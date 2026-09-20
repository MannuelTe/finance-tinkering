"""Offline tests for the router and the MCP server, including real protocol round-trips."""

import asyncio

import pytest

pytest.importorskip("mcp")

from mcp.client import Client  # noqa: E402

from overfit_hmm import mcp_server  # noqa: E402
from overfit_hmm.router import route_question  # noqa: E402

EXPECTED_TOOLS = {
    "route_small_business_question", "blocked_split_layout", "bayes_filter_step",
    "select_hmm_order", "overfitting_study_results",
}


def test_router_math_governance_and_out_of_scope() -> None:
    math_case = route_question("How many regimes should my HMM have? Is it overfit?")
    assert math_case["route"] == "mathematical" and "select_hmm_order" in math_case["suggested_tools"]
    gov = route_question("Which tax form and board duties apply to our GmbH regime?")
    assert gov["route"] == "governance_declined" and gov["suggested_tools"] == []
    assert route_question("Best pizza in Winterthur?")["route"] == "out_of_scope"


def test_governance_wins_over_math_terms() -> None:
    assert route_question("Bayes probability of a lawsuit")["route"] == "governance_declined"


def test_bayes_step_matches_hand_calculation() -> None:
    out = mcp_server.bayes_filter_step([0.5, 0.5], [[0.9, 0.1], [0.2, 0.8]], [0.1, 0.4])
    assert out["predicted"] == pytest.approx([0.55, 0.45])
    assert out["predictive_density"] == pytest.approx(0.235)
    assert sum(out["posterior"]) == pytest.approx(1.0)


def test_bayes_step_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        mcp_server.bayes_filter_step([0.5, 0.5], [[0.9, 0.2], [0.2, 0.8]], [0.1, 0.4])
    with pytest.raises(ValueError):
        mcp_server.bayes_filter_step([0.5, 0.5], [[0.9, 0.1], [0.2, 0.8]], [0.0, 0.0])


def test_split_layout_is_purged() -> None:
    out = mcp_server.blocked_split_layout(3000, seed=3)
    assert out["test_blocks"][-1] == [2920, 3000]
    assert out["min_purged_gap_days"] >= out["requested_gap_days"]


def test_features_are_validated() -> None:
    with pytest.raises(ValueError):
        mcp_server.select_hmm_order([[float("nan"), 1.0]] * 700)
    with pytest.raises(ValueError):
        mcp_server.select_hmm_order([[0.0, 1.0]] * 700, candidate_states=[1, 3])


def test_protocol_round_trip() -> None:
    async def scenario() -> None:
        async with Client(mcp_server.server) as client:
            tools = (await client.list_tools()).tools
            assert {t.name for t in tools} == EXPECTED_TOOLS
            assert all(t.annotations and t.annotations.read_only_hint for t in tools)
            result = await client.call_tool(
                "bayes_filter_step",
                {"prior": [0.5, 0.5], "transition": [[0.9, 0.1], [0.2, 0.8]],
                 "likelihood": [0.1, 0.4]},
            )
            assert not result.is_error
            assert result.structured_content["predictive_density"] == pytest.approx(0.235)
            bad = await client.call_tool("bayes_filter_step", {"prior": [1.0]})
            assert bad.is_error
            resources = (await client.list_resources()).resources
            assert any(str(r.uri) == "hmm://overfitting/multiseed-results" for r in resources)
            assert "Zurich" in client.instructions

    asyncio.run(scenario())
