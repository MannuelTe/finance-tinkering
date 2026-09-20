# harness

Turn an investment thesis written in plain text into a mathematical research paper (LaTeX + PDF):
formalised strategy, labelled equations, backtest, bootstrap uncertainty, figures, and an honest
limitations section. Every number in the paper is generated from the backtest, never typed by hand.

The repo also holds `tradebot`, a small generic trading/backtesting toolkit (IBKR paper account or an
in-memory sim). It is separate from the paper pipeline and thesis-free.

> **Research software, not investment advice.** Nothing here is validated for live capital, and
> generated papers describe one historical sample, not future returns.

## Requirements

- [uv](https://docs.astral.sh/uv/) (Python 3.12 environments)
- [tectonic](https://tectonic-typesetting.github.io/) (`brew install tectonic`) to compile LaTeX
- Claude Code for the agent workflow (optional; the deterministic part runs without it)

## Quickstart

1. Put your thesis in `theses/<slug>/thesis.md` (or scaffold with `uv run thesispaper new <slug>`).
2. In Claude Code run `/thesis-to-paper <slug>`. It formalises the thesis into `thesis.yaml` and
   `strategy.py`, writes the thesis-specific math, builds, and reviews the result.
   Without Claude Code, edit `thesis.yaml` / `strategy.py` yourself and run `uv run thesispaper all <slug>`.
3. Open `theses/<slug>/paper.pdf`.

Try the bundled example (synthetic prices, runs offline):

```bash
uv sync
uv run thesispaper all example     # -> theses/example/paper.pdf
```

Other commands: `thesispaper new|check|run|build|all <slug>`. To use real prices set
`data_source: yfinance` in `thesis.yaml`.

## Layout

```
src/thesispaper/     the paper pipeline (spec, data, metrics, strategy, backtest, results, figures, latex, cli)
src/tradebot/        generic trading infra (brokers, sizing, risk, persistence, backtest)
templates/           LaTeX preamble, paper template, one template per generic chapter
theses/<slug>/       thesis.md, thesis.yaml, strategy.py, sections/thesis_math.tex; generated: results.json,
                     numbers.tex, figures/, paper.tex, paper.pdf
.claude/commands/    /thesis-to-paper orchestration prompt
AGENTS.md            map of the repo for AI agents (architecture, conventions, rules)
```

## The trading infra (`tradebot`)

`tradebot` is independent of the paper pipeline: it has a simulated broker and an IBKR adapter, a
weights-to-orders sizer, a risk gate (kill switch, notional cap), persistence, and a backtest. See
`ARCHITECTURE.md`. Safety notes:

- Use **paper mode only**. Live trading is not supported or validated.
- Keep credentials in `.env` (git-ignored); commit only `.env.example`. Never commit IBKR, database or
  Telegram secrets. See `SECURITY.md`.

## Development

```bash
uv run ruff check .
uv run pytest            # offline; set THESIS_ONLINE=1 to include network tests
```

## Troubleshooting

- `ModuleNotFoundError: No module named 'thesispaper'` right after `uv sync` on macOS: the editable-install
  `.pth` file got the "hidden" flag (seen in iCloud/synced folders). Fix with
  `chflags nohidden .venv/lib/python3.12/site-packages/*.pth`, or keep the repo outside a synced folder.
- `tectonic: command not found`: `brew install tectonic`.
