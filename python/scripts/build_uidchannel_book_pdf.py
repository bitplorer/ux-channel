#!/usr/bin/env python3
"""Build docs/book/UX_CHANNEL_BOOK.pdf from UX_CHANNEL_BOOK.md"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
MD = ROOT / "docs/book/UX_CHANNEL_BOOK.md"
OUT = ROOT / "docs/book/UX_CHANNEL_BOOK.pdf"


class BookPDF(FPDF):
    def header(self):
        if self.page_no() <= 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 6, "The Ui-Channel Book | v0.1.0", align="L")
        self.ln(8)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")


def clean(s: str) -> str:
    repl = {
        "\u2014": "-", "\u2013": "-", "\u2192": "->", "\u2190": "<-",
        "\u2026": "...", "\u00a0": " ", "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"', "\u2022": "*", "\u2265": ">=",
        "\u00d7": "x", "\u2011": "-",
    }
    for a, b in repl.items():
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


def usable_width(pdf: FPDF) -> float:
    return pdf.w - pdf.l_margin - pdf.r_margin


def write_body(pdf: FPDF, text: str, size: int = 10):
    text = clean(text)
    if not text.strip():
        pdf.ln(3)
        return
    pdf.set_font("Helvetica", size=size)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(usable_width(pdf), 5, text)


def write_heading(pdf: FPDF, text: str, level: int):
    text = clean(text)
    pdf.ln(3 if level > 1 else 5)
    if level == 1:
        pdf.set_font("Helvetica", "B", 16)
        h = 8
    elif level == 2:
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(20, 45, 90)
        h = 7
    else:
        pdf.set_font("Helvetica", "B", 11)
        h = 6
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(usable_width(pdf), h, text)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)


def write_code(pdf: FPDF, lines: list[str]):
    pdf.ln(1)
    pdf.set_font("Courier", size=7.5)
    pdf.set_fill_color(242, 243, 247)
    pdf.set_text_color(25, 28, 35)
    w = usable_width(pdf)
    for cl in lines:
        cl = clean(cl)
        if len(cl) > 100:
            cl = cl[:97] + "..."
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w, 3.8, cl if cl.strip() else " ", fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def write_table(pdf: FPDF, rows: list[list[str]]):
    rows = [r for r in rows if not all(re.match(r"^:?-+:?$", c or "") for c in r)]
    if not rows:
        return
    ncols = max(len(r) for r in rows)
    w = usable_width(pdf) / ncols
    pdf.ln(1)
    for ri, row in enumerate(rows):
        while len(row) < ncols:
            row.append("")
        pdf.set_font("Helvetica", "B" if ri == 0 else "", 7.5)
        x0 = pdf.l_margin
        y0 = pdf.get_y()
        max_h = 5
        if y0 > pdf.h - 25:
            pdf.add_page()
            y0 = pdf.get_y()
        for ci, cell in enumerate(row):
            pdf.set_xy(x0 + ci * w, y0)
            pdf.cell(w, max_h, clean(cell)[:36], border=1)
        pdf.set_y(y0 + max_h)
    pdf.ln(3)


def main() -> int:
    if not MD.is_file():
        print("missing", MD, file=sys.stderr)
        return 1
    text = MD.read_text(encoding="utf-8")
    pdf = BookPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    pdf.set_margins(16, 16, 16)

    pdf.ln(40)
    pdf.set_font("Helvetica", "B", 24)
    pdf.multi_cell(usable_width(pdf), 12, "The Ui-Channel Book", align="C")
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 12)
    pdf.multi_cell(
        usable_width(pdf),
        7,
        clean(
            "Intent -> Action -> Result(ops)\n"
            "Server-driven UI control plane for Python\nVersion 0.1.0"
        ),
        align="C",
    )
    pdf.ln(16)
    pdf.set_font("Helvetica", "I", 10)
    pdf.multi_cell(
        usable_width(pdf),
        5,
        "Basics through enterprise patterns, security, testing, recipes, API.",
        align="C",
    )
    pdf.add_page()

    lines = text.splitlines()
    i = 0
    in_code = False
    code_buf: list[str] = []
    table_rows: list[list[str]] = []

    def flush_table():
        nonlocal table_rows
        if table_rows:
            write_table(pdf, table_rows)
            table_rows = []

    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            if in_code:
                write_code(pdf, code_buf)
                code_buf = []
                in_code = False
            else:
                flush_table()
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue
        if "|" in line and line.strip().startswith("|"):
            table_rows.append([c.strip() for c in line.strip().strip("|").split("|")])
            i += 1
            continue
        flush_table()
        if line.startswith("# "):
            write_heading(pdf, line[2:].strip(), 1)
        elif line.startswith("## "):
            write_heading(pdf, line[3:].strip(), 2)
        elif line.startswith("### "):
            write_heading(pdf, line[4:].strip(), 3)
        elif line.strip() == "---":
            pdf.ln(2)
        elif not line.strip():
            pdf.ln(2)
        else:
            body = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
            body = re.sub(r"`([^`]+)`", r"\1", body)
            write_body(pdf, body)
        i += 1
    flush_table()
    if code_buf:
        write_code(pdf, code_buf)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUT))
    print(f"wrote {OUT} ({pdf.page_no()} pages, {OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
