import asyncio

from src.agent_tools.web_tools import WebSearchTool, _infer_time_filter


def test_broad_followup_query_is_rejected_before_search():
    result = asyncio.run(WebSearchTool().execute("scores", {}))

    assert result["exit_code"] == 1
    assert "too broad" in result["error"]
    assert "standalone query" in result["error"]
    assert "event, league, team" in result["error"]


def test_current_result_queries_get_freshness_filter():
    assert _infer_time_filter("world cup 2026 day 1 results") == "week"
    assert _infer_time_filter("recent tournament fixtures and scores") == "week"
    assert _infer_time_filter("live election results") == "week"
