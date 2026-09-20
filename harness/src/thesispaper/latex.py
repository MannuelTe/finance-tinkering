"""Assemble paper.tex from templates/ and compile it with tectonic.

PURPOSE: fill string.Template files ($-placeholders) with spec data; no numbers are typed here.
INPUTS: repo root containing templates/{preamble.tex, paper.tex.tmpl, sections/*.tex.tmpl};
        theses/<slug>/{numbers.tex, figures/, sections/*.tex (sections/thesis_math.tex is spliced as chapter 6)}.
OUTPUTS: theses/<slug>/paper.tex and (via `compile_pdf`) paper.pdf.

Section templates whose file stem starts with a digit are always included, in sorted order; other
templates are optional and included only if named in thesis.yaml `sections`. Placeholders available
everywhere: $title $author $slug $abstract $hypotheses $currency $extra_sections $thesis_math and
(paper.tex.tmpl only) $preamble $body. If no template uses $extra_sections / $thesis_math, they are
appended after the last section. Missing templates raise `TemplateError` with a helpful message.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from string import Template

from thesispaper.spec import Thesis


class TemplateError(RuntimeError):
    """Templates missing or LaTeX toolchain unavailable / failing."""


def template_root(root: Path | None) -> Path:
    for base in (Path(root) if root else None, Path.cwd(), Path(__file__).resolve().parents[2]):
        if base and (base / "templates" / "paper.tex.tmpl").exists():
            return base / "templates"
    raise TemplateError(
        "templates/ not found (need templates/paper.tex.tmpl, preamble.tex, sections/*.tex.tmpl); "
        "run from the repo root or pass --root"
    )


def tex_escape(s: str) -> str:
    return re.sub(r"(?<!\\)([&%#_])", r"\\\1", s)


def _hypotheses(spec: Thesis) -> str:
    if not spec.hypotheses:
        return ""
    items = "\n".join(f"  \\item[{tex_escape(h.id)}] {h.statement}" for h in spec.hypotheses)
    return f"\\begin{{itemize}}\n{items}\n\\end{{itemize}}"


def _read_dir(paths: list[Path]) -> str:
    return "\n\n".join(p.read_text() for p in paths)


def assemble(spec: Thesis, root: Path | None = None) -> str:
    tdir = template_root(root)
    sec_files = sorted((tdir / "sections").glob("*.tex.tmpl"))
    chosen = [p for p in sec_files if p.name[0].isdigit() or p.name[: -len(".tex.tmpl")] in spec.sections]
    extras = [spec.directory / e for e in spec.extra_sections]
    missing = [str(p) for p in extras if not p.exists()]
    if missing:
        raise TemplateError(f"extra_sections not found: {missing}")
    math_path = spec.directory / "sections" / "thesis_math.tex"
    ctx = {
        "title": tex_escape(spec.title), "author": tex_escape(spec.author), "slug": spec.slug,
        "abstract": spec.summary, "hypotheses": _hypotheses(spec),
        "currency": spec.base_currency,
        "extra_sections": _read_dir(extras),
        "thesis_math": math_path.read_text() if math_path.exists() else "",
    }
    parts = [Template(p.read_text()).safe_substitute(ctx) for p in chosen]
    used = {k: any(f"${k}" in p.read_text() or f"${{{k}}}" in p.read_text() for p in chosen)
            for k in ("extra_sections", "thesis_math")}
    for k in ("extra_sections", "thesis_math"):
        if not used[k] and ctx[k]:
            parts.append(ctx[k])
    preamble = (tdir / "preamble.tex").read_text() if (tdir / "preamble.tex").exists() else ""
    ctx.update(preamble=preamble, body="\n\n".join(parts))
    text = Template((tdir / "paper.tex.tmpl").read_text()).safe_substitute(ctx)
    if "numbers.tex" not in text:
        text = text.replace("\\begin{document}", "\\input{numbers.tex}\n\\begin{document}", 1)
    return text


def write_paper(spec: Thesis, root: Path | None = None) -> Path:
    path = spec.directory / "paper.tex"
    path.write_text(assemble(spec, root))
    return path


def compile_pdf(spec: Thesis) -> Path:
    exe = shutil.which("tectonic")
    if exe is None:
        raise TemplateError("`tectonic` not found on PATH (install: brew install tectonic)")
    proc = subprocess.run([exe, "paper.tex"], cwd=spec.directory, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise TemplateError(f"tectonic failed:\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
    return spec.directory / "paper.pdf"
