#!/usr/bin/env python3
"""Run a local Playwright smoke test over everyday browser actions."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BROWSERS = ROOT / ".playwright-browsers"
FIXTURE = ROOT / "tests" / "fixtures" / "browser_actions_smoke.html"
SCREENSHOT = ROOT / "reports" / "playwright_daily_smoke.png"

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(BROWSERS))

from playwright.sync_api import sync_playwright  # noqa: E402


def one(page, test_id: str, label: str):
    locator = page.get_by_test_id(test_id)
    count = locator.count()
    if count != 1:
        raise AssertionError(f"{label} expected 1 element, saw {count}")
    return locator


def main() -> None:
    if not FIXTURE.exists():
        raise SystemExit(f"Missing fixture: {FIXTURE}")

    SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
    results: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
        page = context.new_page()
        page.goto(FIXTURE.as_uri())

        one(page, "search", "Search input").fill("weather meeting groceries")
        one(page, "search-button", "Search button").click()
        results.append(one(page, "search-result", "Search result").inner_text())

        one(page, "task-input", "Task input").fill("Review today's priorities")
        one(page, "task-input", "Task input").press("Enter")
        one(page, "task-done", "Task checkbox").check()
        results.append(one(page, "task-list", "Task list").inner_text())

        one(page, "meeting-title", "Meeting title").fill("Planning sync")
        one(page, "meeting-time", "Meeting time").select_option("13:30")
        one(page, "save-meeting", "Save meeting").click()
        results.append(one(page, "meeting-result", "Meeting result").inner_text())

        one(page, "draft-note", "Draft note").fill("Agenda: priorities, blockers, follow-ups.")
        one(page, "confirm-box", "Ready checkbox").check()
        one(page, "copy-note", "Copy note").click()
        results.append(page.evaluate("navigator.clipboard.readText()"))

        status = one(page, "status", "Status").inner_text()
        page.screenshot(path=str(SCREENSHOT), full_page=True)
        browser.close()

    print(
        json.dumps(
            {
                "ok": True,
                "fixture": str(FIXTURE),
                "screenshot": str(SCREENSHOT),
                "status": status,
                "results": results,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
