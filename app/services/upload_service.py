from __future__ import annotations

import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import UploadFile
import pdfplumber
import io


def table_to_markdown(table: List[List[Optional[str]]]) -> str:
    """
    Convert a pdfplumber table to simple markdown.

    Each row is a list of cell strings.
    """
    if not table:
        return ""

    header: List[Optional[str]] = table[0]
    rows: List[List[Optional[str]]] = table[1:]

    def fmt_row(row: List[Optional[str]]) -> str:
        # Handle None cells
        return "| " + " | ".join((cell or "").strip() for cell in row) + " |"

    md: List[str] = []
    md.append(fmt_row(header))
    md.append("| " + " | ".join("---" for _ in header) + " |")
    for r in rows:
        md.append(fmt_row(r))

    return "\n".join(md)


def extract_invoice_text_from_path(pdf_path: str | Path) -> List[Dict[str, Any]]:
    """
    Extract text + tables from an invoice PDF into a list of documents.

    Document format:
    {
        "text": str,
        "metadata": {
            "source_file": str,
            "page": int,
        }
    }
    """
    pdf_path = Path(pdf_path)
    docs: List[Dict[str, Any]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            # Extract normal text
            raw_text: Optional[str] = page.extract_text()
            text: str = raw_text or ""

            # Extract tables
            tables = page.extract_tables() or []
            table_texts: List[str] = []

            for t_idx, table in enumerate(tables):
                markdown_table = table_to_markdown(table)
                if markdown_table.strip():
                    table_texts.append(f"Table {t_idx + 1}:\n{markdown_table}")

            combined: str = text
            if table_texts:
                combined += "\n\n" + "\n\n".join(table_texts)

            combined = re.sub(r"[ \t]+", " ", combined)
            combined = re.sub(r"\n{3,}", "\n\n", combined) 

            if combined.strip():
                docs.append(
                    {
                        "text": combined.strip(),
                        "metadata": {
                            "source_file": str(pdf_path.name),
                            "page": page_number,
                        },
                    }
                )

    return docs

def extract_invoice_text_from_file(file: UploadFile) -> List[Dict[str, Any]]:
    """
    Extract text + tables from an invoice PDF into a list of documents.

    Document format:
    {
        "text": str,
        "metadata": {
            "source_file": str,
            "page": int,
        }
    }
    """

    docs: List[Dict[str, Any]] = []

    # Ensure we're at the start of the uploaded file, read bytes and wrap in BytesIO
    try:
        file.file.seek(0)
    except Exception:
        pass
    pdf_bytes = file.file.read()
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        extract_invoice_pdf(file.filename, docs, pdf)
    return docs

def extract_invoice_pdf(filename, docs, pdf):
    for page_number, page in enumerate(pdf.pages, start=1):
            # Extract normal text
        raw_text: Optional[str] = page.extract_text()
        text: str = raw_text or ""

            # Extract tables
        tables = page.extract_tables() or []
        table_texts: List[str] = []

        for t_idx, table in enumerate(tables):
            markdown_table = table_to_markdown(table)
            if markdown_table.strip():
                table_texts.append(f"Table {t_idx + 1}:\n{markdown_table}")

        combined: str = text
        if table_texts:
            combined += "\n\n" + "\n\n".join(table_texts)

        combined = re.sub(r"[ \t]+", " ", combined)
        combined = re.sub(r"\n{3,}", "\n\n", combined) 

        if combined.strip():
            docs.append(
                    {
                        "text": combined.strip(),
                        "metadata": {
                            "source_file": filename,
                            "page": page_number,
                        },
                    }
                )


if __name__ == "__main__":
    pdf_docs = extract_invoice_text_from_path("C:\\Users\\Neko\\source\\repos\\InvoiceReader\\app\\services\\invoice.pdf")
    for d in pdf_docs:
        page = d["metadata"]["page"]
        print(f"PAGE: {page}")
        print(d["text"], "...\n")
