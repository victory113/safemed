"""Render a Markdown document in docs/ to a submittable PDF.

Usage, from the repository root:

    docker compose exec api python -m scripts.build_report FINAL_REPORT

The document stays authored in Markdown so it lives in version control and
diffs sensibly. The PDF is a build artifact, regenerated rather than edited,
which is the only way the two can be guaranteed not to drift apart.

Internal links between documents (REQUIREMENTS.md, DESIGN.md) are stripped to
plain text, because they point at other files rather than inside this one.
Mermaid blocks are replaced by a short note naming the diagram - they are
rendered by GitHub, not by this converter, and a wall of unrendered diagram
source in a submitted PDF reads worse than a pointer to where it renders.
"""
import re
import sys
from pathlib import Path

import markdown
from xhtml2pdf import pisa

DOCS = Path("/docs")

CSS = """
@page { size: letter portrait; margin: 2.0cm 2.2cm 2.2cm 2.2cm;
        @frame footer { -pdf-frame-content: footer; bottom: 1.1cm;
                        margin-left: 2.2cm; margin-right: 2.2cm; height: 1cm; } }
body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt;
       line-height: 1.45; color: #1a1a1a; }
h1 { font-size: 19pt; color: #0b3b5c; margin: 0 0 4pt 0; border-bottom: 2pt solid #0b3b5c;
     padding-bottom: 4pt; }
h2 { font-size: 13.5pt; color: #0b3b5c; margin: 16pt 0 5pt 0;
     border-bottom: 0.6pt solid #c3d4de; padding-bottom: 2pt; }
h3 { font-size: 11pt; color: #22506e; margin: 11pt 0 3pt 0; }
p  { margin: 0 0 6pt 0; text-align: justify; }
ul, ol { margin: 0 0 6pt 14pt; }
li { margin-bottom: 2pt; }
table { width: 100%; border-collapse: collapse; margin: 6pt 0 9pt 0; font-size: 8.8pt; }
th { background: #e8eff4; color: #0b3b5c; text-align: left; padding: 4pt 5pt;
     border: 0.5pt solid #b9ccd8; font-weight: bold; }
td { padding: 4pt 5pt; border: 0.5pt solid #d3dee5; vertical-align: top; }
code { font-family: Courier, monospace; font-size: 8.5pt; background: #f2f5f7; }
pre { background: #f5f7f9; border-left: 2.5pt solid #0b3b5c; padding: 6pt 8pt;
      font-family: Courier, monospace; font-size: 8pt; margin: 6pt 0; }
blockquote { border-left: 2.5pt solid #c9a227; background: #fdfaf0;
             padding: 5pt 9pt; margin: 7pt 0; }
hr { border: 0; border-top: 0.5pt solid #ccd8df; margin: 10pt 0; }
.note { color: #5a6b76; font-style: italic; font-size: 9pt;
        background: #f6f8f9; padding: 5pt 8pt; border: 0.5pt dashed #c3d4de; }
#footer { text-align: center; color: #8a99a3; font-size: 7.5pt; }
"""


def transform(md_text: str) -> str:
    """Make the Markdown safe and sensible for print."""
    # Mermaid renders on GitHub, not here. Name the diagram instead of
    # dumping its source into the PDF.
    def name_diagram(match: re.Match) -> str:
        body = match.group(1)
        kind = body.strip().split("\n", 1)[0].strip()
        label = {
            "graph TD": "module dependency diagram",
            "graph LR": "runtime container diagram",
            "erDiagram": "entity-relationship diagram",
            "sequenceDiagram": "sequence diagram",
        }.get(kind, "diagram")
        return (
            f'\n<p class="note">[{label} — renders in DESIGN.md '
            f"on GitHub]</p>\n"
        )

    md_text = re.sub(r"```mermaid\n(.*?)```", name_diagram, md_text, flags=re.S)

    # Links to sibling documents become plain text; a PDF reader cannot
    # follow them, and a blue word that does nothing is worse than a name.
    md_text = re.sub(r"\[([^\]]+)\]\((?!https?:)[^)]+\)", r"\1", md_text)

    # The in-page table of contents is meaningless without working anchors.
    md_text = re.sub(
        r"## Table of Contents.*?(?=\n---)", "", md_text, flags=re.S
    )

    # The base-14 PDF fonts cover WinAnsi only. An arrow has no glyph and
    # comes out as a blank box, which is worse than an ASCII arrow - and
    # silently so, which is how a submitted document ends up with holes in
    # it. Em-dashes and curly quotes are in WinAnsi and are left alone.
    for bad, good in (
        ("→", "->"),   # →
        ("←", "<-"),   # ←
        ("↑", "^"),    # ↑
        ("↓", "v"),    # ↓
        ("✓", "yes"),  # ✓
        ("✗", "no"),   # ✗
        ("≤", "<="),   # ≤
        ("≥", ">="),   # ≥
        ("×", "x"),    # ×
        # Box drawing and solid arrowheads, used by the ASCII diagrams in the
        # handbook. Mapped to the nearest ASCII so the diagram stays readable
        # rather than becoming a grid of blank boxes.
        ("─", "-"), ("│", "|"), ("┌", "+"), ("┐", "+"),
        ("└", "+"), ("┘", "+"), ("├", "+"), ("┤", "+"),
        ("┬", "+"), ("┴", "+"), ("┼", "+"),
        ("►", ">"), ("◄", "<"), ("▲", "^"), ("▼", "v"),
        ("•", "-"),
    ):
        md_text = md_text.replace(bad, good)
    return md_text


def warn_about_missing_glyphs(md_text: str, stem: str) -> None:
    """Name every character the PDF fonts cannot draw, loudly.

    The table above will always be one character behind the next document.
    The failure it guards against is silent - a glyph the base-14 fonts lack
    becomes a blank box, and nobody notices until the thing has been handed
    in. So rather than trust the table to be complete, ask the encoding
    itself which characters survive, and say which ones do not.
    """
    missing: dict[str, int] = {}
    for char in md_text:
        try:
            char.encode("cp1252")  # what the base-14 fonts actually cover
        except UnicodeEncodeError:
            missing[char] = missing.get(char, 0) + 1
    if not missing:
        return
    print(f"WARNING: {stem}.md has characters the PDF fonts cannot draw.")
    print("         They will appear as blank boxes. Add them to transform().")
    for char, count in sorted(missing.items()):
        print(f"         U+{ord(char):04X}  {char!r}  x{count}")


def build(stem: str) -> Path:
    source = DOCS / f"{stem}.md"
    if not source.exists():
        raise SystemExit(f"No such document: {source}")

    transformed = transform(source.read_text(encoding="utf-8"))
    warn_about_missing_glyphs(transformed, stem)

    html_body = markdown.markdown(
        transformed,
        extensions=["tables", "fenced_code", "sane_lists"],
    )
    html = (
        f"<html><head><meta charset='utf-8'><style>{CSS}</style></head>"
        f"<body><div id='footer'>SafeMed — CSCI 4490 Software Engineering — "
        f"Fall 2026 — page <pdf:pagenumber></div>{html_body}</body></html>"
    )

    out = DOCS / f"{stem}.pdf"
    with out.open("wb") as handle:
        result = pisa.CreatePDF(html, dest=handle, encoding="utf-8")
    if result.err:
        raise SystemExit(f"PDF generation reported {result.err} error(s)")

    print(f"Wrote {out}  ({out.stat().st_size // 1024} KB)")
    return out


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "FINAL_REPORT")
