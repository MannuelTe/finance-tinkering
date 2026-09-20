"""PURPOSE: route small-business questions to the mathematical tools or decline governance topics.
INPUTS: a free-text question.
OUTPUTS: a routing decision (route, matched terms, suggested tools, note).

Deliberately transparent keyword rules, no model calls. A question is handled only if it is
purely mathematical; anything touching governance, legal, tax, regulatory or compliance
matters is declined with a referral, because a maths tool must not pose as advice.
"""

import re
from typing import Any

GOVERNANCE_TERMS = (
    "governance", "legal", "law", "contract", "incorporat", "gmbh", "shareholder", "director",
    "board", "bylaw", "articles of association", "tax", "vat", "gst", "compliance", "regulat",
    "licen", "liabilit", "audit", "aml", "kyc", "insolven", "bankrupt", "employment",
    "labour", "labor", "permit", "trademark", "patent", "lawsuit", "fiduciary",
)

# term -> tools that can help; the tools are defined in mcp_server.py
MATH_TERMS: dict[str, tuple[str, ...]] = {
    "regime": ("select_hmm_order", "bayes_filter_step"),
    "hidden markov": ("select_hmm_order", "bayes_filter_step"),
    "hmm": ("select_hmm_order", "bayes_filter_step"),
    "markov": ("bayes_filter_step",),
    "bayes": ("bayes_filter_step",),
    "posterior": ("bayes_filter_step",),
    "probability": ("bayes_filter_step",),
    "overfit": ("blocked_split_layout", "select_hmm_order", "overfitting_study_results"),
    "validation": ("blocked_split_layout", "select_hmm_order"),
    "cross-validation": ("blocked_split_layout",),
    "train": ("blocked_split_layout",),
    "backtest": ("blocked_split_layout", "overfitting_study_results"),
    "sharpe": ("overfitting_study_results",),
    "volatility": ("select_hmm_order",),
    "seasonal": ("select_hmm_order",),
    "cash flow": ("select_hmm_order",),
    "demand": ("select_hmm_order",),
}

GOVERNANCE_NOTE = (
    "This server only does mathematics and does not give legal, tax, regulatory, accounting or "
    "governance advice. Please ask a qualified professional in the relevant jurisdiction."
)
NO_MATCH_NOTE = (
    "No mathematical topic recognised. This server offers hidden-Markov-model regime tools, "
    "Bayes filtering and purged block validation; rephrase in those terms or use another tool."
)


def _find(text: str, terms: tuple[str, ...]) -> list[str]:
    return [t for t in terms if re.search(rf"(?<![a-z]){re.escape(t)}", text)]


def route_question(question: str) -> dict[str, Any]:
    text = question.lower()
    governance = _find(text, GOVERNANCE_TERMS)
    if governance:
        return {"route": "governance_declined", "matched_terms": governance,
                "suggested_tools": [], "note": GOVERNANCE_NOTE}
    matched = _find(text, tuple(MATH_TERMS))
    if not matched:
        return {"route": "out_of_scope", "matched_terms": [], "suggested_tools": [],
                "note": NO_MATCH_NOTE}
    tools = sorted({tool for term in matched for tool in MATH_TERMS[term]})
    return {"route": "mathematical", "matched_terms": matched, "suggested_tools": tools,
            "note": "Purely mathematical question; call the suggested tools."}
