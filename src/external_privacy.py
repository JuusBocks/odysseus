"""Privacy redaction for prompts sent to external teacher models.

The local/student model can see the user's full context. External teacher
models should only receive the minimum useful brief, with common secrets and
PII replaced by stable placeholders.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class RedactionReport:
    text: str
    redactions: List[Dict[str, Any]]

    @property
    def count(self) -> int:
        return sum(int(item.get("count") or 0) for item in self.redactions)


_SECRET_NAME = (
    r"(?:api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|"
    r"bearer|password|passwd|pwd|secret|client[_-]?secret|private[_-]?key|"
    r"session[_-]?key|cookie|credential)"
)

_FIELD_SECRET_RE = re.compile(
    rf"(?P<prefix>\b{_SECRET_NAME}\b\s*[:=]\s*['\"]?)(?P<value>[^\s'\",;}}]{{6,}})",
    re.IGNORECASE,
)
_HEADER_SECRET_RE = re.compile(
    r"(?P<prefix>\b(?:Authorization|X-API-Key|Api-Key)\s*:\s*(?:Bearer\s+)?)(?P<value>[A-Za-z0-9._~+/=-]{10,})",
    re.IGNORECASE,
)
_CLI_SECRET_RE = re.compile(
    rf"(?P<prefix>\s--(?:api-key|token|password|secret|hf-token)\s+)(?P<value>[^\s'\";]{{6,}})",
    re.IGNORECASE,
)
_PEM_PRIVATE_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.IGNORECASE,
)
_COMMON_TOKEN_RE = re.compile(
    r"\b("
    r"sk-[A-Za-z0-9_-]{16,}|"
    r"nvapi-[A-Za-z0-9_-]{16,}|"
    r"hf_[A-Za-z0-9]{16,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|"
    r"gh[pousr]_[A-Za-z0-9_]{20,}|"
    r"xox[baprs]-[A-Za-z0-9-]{16,}|"
    r"AIza[0-9A-Za-z_-]{20,}|"
    r"AKIA[0-9A-Z]{16}"
    r")\b"
)
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\w)"
)
_DOB_RE = re.compile(
    r"(?P<prefix>\b(?:dob|date of birth|birthdate)\b\s*[:=]?\s*)"
    r"(?P<value>(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|[A-Za-z]+ \d{1,2},? \d{4}))",
    re.IGNORECASE,
)
_CARD_CANDIDATE_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


class _Redactor:
    def __init__(self) -> None:
        self._seen: Dict[tuple[str, str], str] = {}
        self._counts: Dict[str, int] = {}

    def placeholder(self, label: str, value: str) -> str:
        key = (label, value)
        if key in self._seen:
            return self._seen[key]
        self._counts[label] = self._counts.get(label, 0) + 1
        token = f"[REDACTED_{label}_{self._counts[label]}]"
        self._seen[key] = token
        return token

    def report(self, text: str) -> RedactionReport:
        return RedactionReport(
            text=text,
            redactions=[
                {"label": label.lower(), "count": count}
                for label, count in sorted(self._counts.items())
            ],
        )


def _luhn_valid(digits: str) -> bool:
    total = 0
    alt = False
    for ch in reversed(digits):
        n = ord(ch) - 48
        if alt:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        alt = not alt
    return total > 0 and total % 10 == 0


def redact_text_for_external_model(text: Any) -> RedactionReport:
    """Return text safe to send to an external teacher model.

    This is intentionally deterministic and local. It catches common secrets and
    personal identifiers, but it is not a proof that arbitrary sensitive prose
    was removed; the student prompt still tells the local model to summarize
    private details as placeholders before calling the teacher.
    """
    raw = "" if text is None else str(text)
    redactor = _Redactor()
    out = raw

    def whole(label: str):
        def repl(match: re.Match[str]) -> str:
            return redactor.placeholder(label, match.group(0))
        return repl

    def value_only(label: str):
        def repl(match: re.Match[str]) -> str:
            return f"{match.group('prefix')}{redactor.placeholder(label, match.group('value'))}"
        return repl

    out = _PEM_PRIVATE_RE.sub(whole("PRIVATE_KEY"), out)
    out = _FIELD_SECRET_RE.sub(value_only("SECRET"), out)
    out = _HEADER_SECRET_RE.sub(value_only("SECRET"), out)
    out = _CLI_SECRET_RE.sub(value_only("SECRET"), out)
    out = _COMMON_TOKEN_RE.sub(whole("TOKEN"), out)
    out = _DOB_RE.sub(value_only("DOB"), out)
    out = _SSN_RE.sub(whole("SSN"), out)
    out = _EMAIL_RE.sub(whole("EMAIL"), out)
    out = _PHONE_RE.sub(whole("PHONE"), out)

    def card_repl(match: re.Match[str]) -> str:
        candidate = match.group(0)
        digits = re.sub(r"\D", "", candidate)
        if len(digits) < 13 or len(digits) > 19 or not _luhn_valid(digits):
            return candidate
        return redactor.placeholder("PAYMENT_CARD", candidate)

    out = _CARD_CANDIDATE_RE.sub(card_repl, out)
    return redactor.report(out)


def redact_messages_for_external_model(messages: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], RedactionReport]:
    """Redact string content inside OpenAI-style message dicts."""
    combined: List[Dict[str, Any]] = []
    reports: List[RedactionReport] = []
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        copy = dict(msg)
        content = copy.get("content")
        if isinstance(content, str):
            report = redact_text_for_external_model(content)
            copy["content"] = report.text
            reports.append(report)
        elif isinstance(content, list):
            new_parts = []
            for part in content:
                if isinstance(part, dict):
                    part_copy = dict(part)
                    for key in ("text", "content"):
                        if isinstance(part_copy.get(key), str):
                            report = redact_text_for_external_model(part_copy[key])
                            part_copy[key] = report.text
                            reports.append(report)
                    new_parts.append(part_copy)
                else:
                    new_parts.append(part)
            copy["content"] = new_parts
        combined.append(copy)

    counts: Dict[str, int] = {}
    for report in reports:
        for item in report.redactions:
            label = str(item.get("label") or "")
            counts[label] = counts.get(label, 0) + int(item.get("count") or 0)
    summary = RedactionReport(
        text="",
        redactions=[{"label": label, "count": count} for label, count in sorted(counts.items())],
    )
    return combined, summary

