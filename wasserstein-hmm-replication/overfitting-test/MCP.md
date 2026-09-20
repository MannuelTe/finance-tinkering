# MCP server: HMM regime maths and blocked validation

A read-only [Model Context Protocol](https://modelcontextprotocol.io/specification/2026-07-28) server (JSON-RPC 2.0; stdio and streamable HTTP) for the mathematics in this project. It works with any MCP client, including Meta's **Muse Code** ([docs](https://dev.meta.ai/docs/muse-code/extending)).

**Scope.** Purely mathematical topics: hidden-Markov regime models, Bayes filtering, purged block validation and the stored results of the overfitting study. Governance, legal, tax, regulatory and compliance questions are declined by design. This is not investment, legal or tax advice.

**Intended audience.** Small-business and finance questions in **Zurich, Zug, Winterthur and the Lower Mainland of British Columbia**. The mathematics is region-agnostic; the regions appear in the server metadata and this page so that people searching for them can find the tools.

## Tools

All tools carry `readOnlyHint: true`, validate their inputs with bounds (at most 6,000 rows, 30 columns, 8 states), return structured JSON, and report bad input as an MCP tool error (`isError: true`).

| Tool | What it does |
|---|---|
| `route_small_business_question` | Free-text question in, decision out: `mathematical` (with the tools that help), `governance_declined` (with a referral note) or `out_of_scope`. Call this first. |
| `blocked_split_layout` | Purged random-block train/test layout (`\|train\|gap\|TEST\|gap\|train\| ... \|gap\|TEST(last days)`) with the smallest purged gap actually found. |
| `bayes_filter_step` | One HMM Bayes update: Markov predict step, likelihood update, renormalise; returns the predictive density. |
| `select_hmm_order` | Chooses the number of states `K` for your features by `blocked` validation or the original `last_window` rule. Needs `hmmlearn` and about 600 or more rows for `blocked`. |
| `overfitting_study_results` | The stored 30-seed results (Sharpe difference, paired tests, block bootstrap, by-year splits). Also available as the resource `hmm://overfitting/multiseed-results`. |

The router is a transparent keyword table in [`router.py`](src/overfit_hmm/router.py). Where a question touches both maths and governance, governance wins and the question is declined. That file is also the place to add further small-business topics later.

## Install and run

```bash
cd paper-replication && uv sync && uv pip install "mcp>=2.2,<3"     # one environment for both projects
cd ../overfitting-test
export PYTHONPATH="src:../paper-replication/src"
../paper-replication/.venv/bin/python -m overfit_hmm.mcp_server                                # stdio (default)
../paper-replication/.venv/bin/python -m overfit_hmm.mcp_server --transport streamable-http --port 8765   # http://127.0.0.1:8765/mcp
```

Tested with the official Python SDK client over both stdio and streamable HTTP (`tests/test_mcp.py` covers the protocol round trip: `tools/list`, `tools/call`, error results, resources and instructions).

## Connect from Muse Code

Muse Code declares servers under `mcp_servers` in its settings file. Replace `/ABS` with your absolute path. Stdio clients start the server with a **minimal environment**, so `PYTHONPATH` must be given explicitly in `env`:

```json
{
  "mcp_servers": {
    "overfit-hmm": {
      "transport": "stdio",
      "command": "/ABS/wasserstein-hmm-replication/paper-replication/.venv/bin/python",
      "args": ["-m", "overfit_hmm.mcp_server"],
      "env": {
        "PYTHONPATH": "/ABS/wasserstein-hmm-replication/overfitting-test/src:/ABS/wasserstein-hmm-replication/paper-replication/src"
      },
      "mode": "optional"
    }
  }
}
```

For a running HTTP server use `url` (and optional `headers`) instead of `command`/`args`, for example `"url": "http://127.0.0.1:8765/mcp"`; check the exact `transport` value for HTTP in the Muse Code documentation.

## Notes on safety

- Every tool is read-only and none sends data anywhere. MCP tools are not sandboxed by the client, so review any server you connect.
- The HTTP transport has **no authentication** and binds to `127.0.0.1` by default. Do not expose it to a network as is; put it behind an OAuth 2.1 front end first (Muse Code supports `muse mcp login <server>`).
- What was tested: the official Python SDK client over stdio and streamable HTTP. It has **not** been tested against Muse Code itself.
