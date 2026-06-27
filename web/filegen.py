"""Génération de fichiers bureautiques pour VindIA.

VindIA (côté n8n) ne sait produire que du texte. Elle renvoie son contenu dans
le marqueur [[FICHIER:nom.ext]] ... [[/FICHIER]]. Pour les formats binaires
(Word, Excel, PowerPoint, PDF), la page poste ce contenu ici et reçoit le vrai
fichier. Aucun stockage : on construit en mémoire et on renvoie les octets.

Conventions de contenu attendues de VindIA :
  - .docx / .pdf : markdown simple (# titres, - puces, paragraphes)
  - .xlsx        : CSV (séparateur , ; ou tabulation, auto-détecté)
  - .pptx        : diapositives séparées par une ligne contenant seulement ---
                   (1re ligne de chaque diapo = titre, le reste = puces)
"""

from __future__ import annotations

import csv
import io
import re

_DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Extensions binaires prises en charge -> content-type
OFFICE_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "pdf": "application/pdf",
}


def _strip_inline(text: str) -> str:
    """Retire le gras/italique/`code` markdown inline."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    return text


def _build_docx(content: str) -> bytes:
    from docx import Document

    doc = Document()
    for raw in content.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("### "):
            doc.add_heading(_strip_inline(line[4:].strip()), level=3)
        elif line.startswith("## "):
            doc.add_heading(_strip_inline(line[3:].strip()), level=2)
        elif line.startswith("# "):
            doc.add_heading(_strip_inline(line[2:].strip()), level=1)
        elif re.match(r"^\s*[-*]\s+", line):
            doc.add_paragraph(_strip_inline(re.sub(r"^\s*[-*]\s+", "", line)), style="List Bullet")
        elif re.match(r"^\s*\d+[.)]\s+", line):
            doc.add_paragraph(_strip_inline(re.sub(r"^\s*\d+[.)]\s+", "", line)), style="List Number")
        else:
            doc.add_paragraph(_strip_inline(line))
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _sniff_rows(content: str):
    text = content.strip("\n")
    sample = text[:2000]
    delim = ","
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
    except Exception:
        for cand in (";", "\t", ","):
            if cand in sample:
                delim = cand
                break
    return list(csv.reader(io.StringIO(text), delimiter=delim))


def _build_xlsx(content: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Feuille1"
    rows = _sniff_rows(content)
    for r, row in enumerate(rows, start=1):
        for c, val in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=val)
            if r == 1:
                cell.font = Font(bold=True)
    # Largeur de colonne approximative
    if rows:
        for c in range(1, max(len(r) for r in rows) + 1):
            width = max((len(str(row[c - 1])) for row in rows if len(row) >= c), default=10)
            ws.column_dimensions[ws.cell(row=1, column=c).column_letter].width = min(max(width + 2, 10), 60)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _build_pptx(content: str) -> bytes:
    from pptx import Presentation
    from pptx.util import Pt

    prs = Presentation()
    blank_title = prs.slide_layouts[1]  # Titre + contenu
    chunks = re.split(r"(?m)^\s*---\s*$", content)
    chunks = [c for c in chunks if c.strip()] or [content]
    for chunk in chunks:
        lines = [l.rstrip() for l in chunk.splitlines() if l.strip()]
        if not lines:
            continue
        slide = prs.slides.add_slide(blank_title)
        title = _strip_inline(re.sub(r"^#+\s*", "", lines[0]))
        slide.shapes.title.text = title
        body = slide.placeholders[1].text_frame
        body.clear()
        first = True
        for line in lines[1:]:
            txt = _strip_inline(re.sub(r"^\s*[-*]\s+", "", line))
            p = body.paragraphs[0] if first else body.add_paragraph()
            p.text = txt
            p.font.size = Pt(18)
            first = False
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _build_pdf(content: str) -> bytes:
    from fpdf import FPDF

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.add_font("DejaVu", "", _DEJAVU)
    pdf.add_font("DejaVu", "B", _DEJAVU_BOLD)

    def cell(text: str, size: int, height: float, bold: bool = False) -> None:
        pdf.set_font("DejaVu", "B" if bold else "", size)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(pdf.epw, height, text, new_x="LMARGIN", new_y="NEXT")

    for raw in content.splitlines():
        line = raw.rstrip()
        if not line.strip():
            pdf.ln(3)
            continue
        if line.startswith("# "):
            cell(_strip_inline(line[2:].strip()), 18, 9, bold=True)
        elif line.startswith("## "):
            cell(_strip_inline(line[3:].strip()), 15, 8, bold=True)
        elif line.startswith("### "):
            cell(_strip_inline(line[4:].strip()), 13, 7, bold=True)
        elif re.match(r"^\s*[-*]\s+", line):
            cell("  •  " + _strip_inline(re.sub(r"^\s*[-*]\s+", "", line)), 11, 6)
        else:
            cell(_strip_inline(line), 11, 6)
    out = pdf.output()
    return bytes(out)


_BUILDERS = {
    "docx": _build_docx,
    "xlsx": _build_xlsx,
    "pptx": _build_pptx,
    "pdf": _build_pdf,
}


def build_file(name: str, content: str) -> tuple[bytes, str]:
    """Construit le fichier binaire. Lève ValueError si l'extension n'est pas gérée."""
    ext = (name.rsplit(".", 1)[-1] if "." in name else "").lower()
    if ext not in _BUILDERS:
        raise ValueError(f"format non supporte: {ext}")
    return _BUILDERS[ext](content or ""), OFFICE_TYPES[ext]
