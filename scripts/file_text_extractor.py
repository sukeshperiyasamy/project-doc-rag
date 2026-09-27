"""
Document Text Extractor and Chunking Utility for SERS Research Knowledge Base.
Supports .docx, .pdf, .pptx, .csv, .txt, .md.
Strictly excludes .xlsx and .xls per project specifications.
"""

import sys
import hashlib
from pathlib import Path

# Parsers
import docx
import pypdf
import pptx
import csv

SOURCE_DIR = Path(r"C:\Users\sukes\Downloads\mtp")
RAG_DIR = Path(r"C:\Research-Knowledge-Base\rag_storage")

EXCLUDED_EXT = {".xlsx", ".xls"}
SUPPORTED_EXT = {".docx", ".pdf", ".csv", ".txt", ".md", ".pptx"}
DUPLICATE_FILES = {"LTA_Complete_Evidence_Report_1.docx"}  # Exact SHA256 duplicate of LTA_Complete_Evidence_Report.docx

def calculate_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def extract_docx(fp: Path) -> str:
    doc = docx.Document(fp)
    text = []
    for p in doc.paragraphs:
        t = p.text.strip()
        if t:
            text.append(t)
    for table in doc.tables:
        for row in table.rows:
            row_txt = [c.text.strip() for c in row.cells if c.text.strip()]
            if row_txt:
                text.append(" | ".join(row_txt))
    return "\n\n".join(text)

def extract_pdf(fp: Path) -> str:
    reader = pypdf.PdfReader(fp)
    text = []
    for page in reader.pages:
        t = page.extract_text()
        if t and t.strip():
            text.append(t.strip())
    return "\n\n".join(text)

def extract_pptx(fp: Path) -> str:
    prs = pptx.Presentation(fp)
    text = []
    for idx, slide in enumerate(prs.slides):
        slide_text = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    t = paragraph.text.strip()
                    if t:
                        slide_text.append(t)
        if slide_text:
            text.append(f"--- Slide {idx + 1} ---\n" + "\n".join(slide_text))
    return "\n\n".join(text)

def extract_text(fp: Path) -> str:
    ext = fp.suffix.lower()
    if ext == ".docx":
        return extract_docx(fp)
    elif ext == ".pdf":
        return extract_pdf(fp)
    elif ext == ".pptx":
        return extract_pptx(fp)
    elif ext in [".txt", ".md", ".csv"]:
        return fp.read_text(encoding="utf-8", errors="ignore")
    return ""

def chunk_text(text: str, target_size: int = 2000, overlap: int = 220) -> list[str]:
    """
    Slices text into ~1800-2200 char windows with ~220 char (~60 token) overlap.
    Splits at natural paragraph (\\n\\n), line (\\n), or sentence (. ) boundaries.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= target_size + 200:
        return [text]

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + target_size, text_len)
        if end < text_len:
            # Look for natural paragraph boundary
            para_break = text.rfind("\n\n", start + int(target_size * 0.75), end + 200)
            if para_break != -1 and para_break > start:
                end = para_break
            else:
                line_break = text.rfind("\n", start + int(target_size * 0.75), end + 150)
                if line_break != -1 and line_break > start:
                    end = line_break
                else:
                    period_break = text.rfind(". ", start + int(target_size * 0.75), end + 100)
                    if period_break != -1 and period_break > start:
                        end = period_break + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break
        start = max(start + 1, end - overlap)

    return chunks
