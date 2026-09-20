"""thesispaper: turn an investment thesis (theses/<slug>/) into a mathematical LaTeX paper.

PURPOSE: pure, typed pipeline spec -> data -> backtest -> results.json/numbers.tex -> paper.pdf.
INPUTS: theses/<slug>/thesis.yaml (+ strategy.py, sections/*.tex).
OUTPUTS: results.json, numbers.tex, figures/, paper.tex, paper.pdf inside the thesis folder.
"""

__version__ = "0.1.0"
