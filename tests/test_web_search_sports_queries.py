import asyncio

from src.agent_tools.web_tools import WebSearchTool, _infer_time_filter


def test_broad_scores_query_is_rejected_before_search():
    result = asyncio.run(WebSearchTool().execute("scores", {}))

    assert result["exit_code"] == 1
    assert "too broad" in result["error"]
    assert "FIFA World Cup 2026" in result["error"]


def test_fifa_results_query_gets_freshness_filter():
    assert _infer_time_filter("fifa world cup 2026 day 1 results") == "week"
    assert _infer_time_filter("recent fifa fixtures and scores") == "week"
