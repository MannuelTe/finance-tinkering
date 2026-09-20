# Mathematical paper

The LaTeX source is `financial_mathematics_of_tradebot.tex`. It uses only conventional TeX Live
packages and includes two existing PDF figures from `../graphics_paper/figures/`.

Compile from this directory with [Tectonic](https://tectonic-typesetting.github.io/):

```bash
mkdir -p ../output/pdf
tectonic financial_mathematics_of_tradebot.tex --outdir ../output/pdf
```

The stable deliverable is `../financial_mathematics_of_tradebot.pdf`. LaTeX auxiliary
files and rendered QA pages are ignored by Git.
