"""Regression: stream_agent_loop emits `rounds_exhausted` only when the round
cap is hit while still working, and NOT on a normal finish.

The decision is a `for/else` in the loop: the `else` runs only if no `break`
fired (break = done / budget / error). A refactor that adds a stray break or
return, or moves the done-break, could silently flip this. See PR #1999 / #1997.
"""

import asyncio
import json

import src.agent_loop as al


def _collect(gen):
    async def _run():
        return [c async for c in gen]
    return asyncio.run(_run())


def _types(chunks):
    out = []
    for c in chunks:
        if c.startswith("data: ") and not c.startswith("data: [DONE]"):
            try:
                out.append(json.loads(c[6:]))
            except Exception:
                pass
    return out


def _patch_common(monkeypatch):
    # Skip RAG/tool-index, MCP, and settings lookups; keep the real loop body,
    # _resolve_tool_blocks, and parse_tool_blocks.
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)

    async def _fake_exec(block, *a, **k):
        return ("bash", {"output": "ok", "exit_code": 0})
    monkeypatch.setattr(al, "execute_tool_block", _fake_exec, raising=False)


def _run_loop(
    monkeypatch,
    round_text,
    max_rounds=2,
    user_content="do a long multi-step task",
    enable_next_step_options=False,
):
    async def _fake_stream(_candidates, messages, **kwargs):
        yield f'data: {json.dumps({"delta": round_text})}\n\n'
        yield "data: [DONE]\n\n"
    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    gen = al.stream_agent_loop(
        "http://x/v1", "m",
        [{"role": "user", "content": user_content}],
        max_rounds=max_rounds,
        relevant_tools={"bash"},
        enable_next_step_options=enable_next_step_options,
    )
    return _types(_collect(gen))


def test_emits_rounds_exhausted_when_cap_hit_mid_task(monkeypatch):
    _patch_common(monkeypatch)
    # Every round returns a tool block -> never "done" -> loop exhausts the cap.
    events = _run_loop(monkeypatch, "```bash\necho hi\n```", max_rounds=2)
    assert any(e.get("type") == "rounds_exhausted" for e in events), events


def test_no_rounds_exhausted_on_normal_finish(monkeypatch):
    _patch_common(monkeypatch)
    # A plain answer (no tool block) -> done-break on round 1 -> no event.
    events = _run_loop(monkeypatch, "All done, here is your answer.", max_rounds=2)
    assert not any(e.get("type") == "rounds_exhausted" for e in events), events


def test_product_plan_finish_does_not_emit_static_next_step_options(monkeypatch):
    _patch_common(monkeypatch)
    events = _run_loop(
        monkeypatch,
        "Here is the concise product plan for ClientPortal Pro.",
        max_rounds=2,
        user_content="I want to build a product called ClientPortal Pro.",
        enable_next_step_options=True,
    )
    assert not any(e.get("type") == "ask_user" for e in events), events


def test_product_plan_finish_does_not_emit_next_step_options_by_default(monkeypatch):
    _patch_common(monkeypatch)
    events = _run_loop(
        monkeypatch,
        "Here is the concise product plan for ClientPortal Pro.",
        max_rounds=2,
        user_content="I want to build a product called ClientPortal Pro.",
    )
    assert not any(e.get("type") == "ask_user" for e in events), events


def test_natural_product_prompt_does_not_emit_static_next_step_options(monkeypatch):
    _patch_common(monkeypatch)
    events = _run_loop(
        monkeypatch,
        "Product vision\nMVP scope\nTechnical architecture\nNext Steps\nDeep dive on security.",
        max_rounds=2,
        user_content=(
            "I want to build a product called ClientPortal Pro.\n\n"
            "It is a SaaS client portal for freelancers, agencies, and small service businesses. "
            "The product should help them manage clients, projects, files, invoices, approvals, "
            "onboarding forms, messages, and project status updates.\n\n"
            "After your first answer, do not stop. Give me a short option list for what we "
            "should do next, like Codex does, so I can choose the next step."
        ),
        enable_next_step_options=True,
    )
    assert not any(e.get("type") == "ask_user" for e in events), events


def test_product_followup_does_not_emit_static_next_step_options_from_recent_context(monkeypatch):
    _patch_common(monkeypatch)
    async def _fake_stream(_candidates, messages, **kwargs):
        yield f'data: {json.dumps({"delta": "Here is a visual product direction and mockup plan."})}\n\n'
        yield "data: [DONE]\n\n"
    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    gen = al.stream_agent_loop(
        "http://x/v1", "m",
        [
            {"role": "user", "content": "I want to build a product called ClientPortal Pro."},
            {"role": "assistant", "content": "Here is the product plan."},
            {"role": "user", "content": "Prior product planning choice"},
            {"role": "assistant", "content": "Here is the MVP scope."},
            {"role": "user", "content": "i need to see a product"},
        ],
        max_rounds=2,
        relevant_tools={"bash"},
        enable_next_step_options=True,
    )
    events = _types(_collect(gen))
    assert not any(e.get("type") == "ask_user" for e in events), events


def test_complex_product_prompt_auto_asks_teacher_when_configured(monkeypatch):
    _patch_common(monkeypatch)
    monkeypatch.setattr(
        al,
        "get_setting",
        lambda key, default=None: {
            "teacher_enabled": True,
            "teacher_model": "nvidia/test",
        }.get(key, default),
        raising=False,
    )

    async def _fake_exec(block, *a, **k):
        if block.tool_type == "ask_teacher":
            return {
                "response": "Teacher architecture critique.",
                "model": "nvidia/test",
                "exit_code": 0,
                "teacher_exchange": {"teacher_model": "nvidia/test", "redaction_count": 0},
            }
        return ("bash", {"output": "ok", "exit_code": 0})

    monkeypatch.setattr(al, "execute_tool_block", _fake_exec, raising=False)
    events = _run_loop(
        monkeypatch,
        "Final product plan using the teacher guidance.",
        max_rounds=2,
        user_content=(
            "I want to build a product called ClientPortal Pro. "
            "Please create product vision, MVP scope, technical architecture, "
            "database model, main user flows, privacy/security concerns, and build plan."
        ),
        enable_next_step_options=True,
    )
    teacher_events = [e for e in events if e.get("tool") == "ask_teacher"]
    assert any(e.get("type") == "tool_start" for e in teacher_events), events
    assert any(e.get("type") == "tool_output" and e.get("teacher_exchange") for e in teacher_events), events
    assert not any(e.get("type") == "ask_user" for e in events), events
