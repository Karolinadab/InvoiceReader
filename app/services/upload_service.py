from __future__ import annotations

from datetime import datetime
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import UploadFile
import pdfplumber
import io
from app.services.invoice import Invoice
from app.services.invoice_item import InvoiceItem
import camelot


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
        return "| " + " | ".join((cell or "").strip() for cell in row) + " |"

    md: List[str] = []
    md.append(fmt_row(header))
    md.append("| " + " | ".join("---" for _ in header) + " |")
    for r in rows:
        md.append(fmt_row(r))

    return "\n".join(md)


def _parse_float(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    # remove non‑breaking spaces and normal spaces used as thousand separators
    raw = str(s).replace("\u00A0", "").replace(" ", "").strip()
    # normalize decimal comma to dot
    raw = raw.replace(",", ".")
    # keep only digits, dot and minus sign
    cleaned = re.sub(r"[^0-9\.\-]", "", raw)
    # if multiple dots, join fractional parts (keep first dot)
    if cleaned.count(".") > 1:
        parts = cleaned.split(".")
        cleaned = parts[0] + "." + "".join(parts[1:])
    if not cleaned or cleaned in {"-", "."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None

def _parse_int(s: Optional[str]) -> Optional[int]:
    f = _parse_float(s)
    return None if f is None else int(f)
    

def extract_invoice_text_from_path(pdf_path: str | Path) -> Invoice:
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
    invoice = Invoice()

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            # Extract normal text
            raw_text: Optional[str] = page.extract_text()
            text: str = raw_text or ""

            # Extract table
            tables = page.extract_tables() or []
            invoice_items: List[InvoiceItem] = []

            if tables:
                invoice_items = tables[0][1:]  # first table contains invoice items

            for _, row in enumerate(invoice_items):  # skip first table which is often header/footer
                invoice_item = InvoiceItem(
                    ordinal_number=_parse_int(row[0]) if row[0] else None,
                    name=row[1] or None,
                    unit=row[2] or None,
                    quantity=_parse_int(row[3]) if row[3] else None,
                    unit_price_netto=_parse_float(row[4]) if row[4] else None,
                    total_price_netto=_parse_float(row[5]) if row[5] else None,
                    tax_rate=_parse_float(row[6]) if row[6] else None,
                    tax_amount=_parse_float(row[7]) if row[7] else None,
                    total_price_gross=_parse_float(row[8]) if row[8] else None
                )
                
                if invoice_item.name:  # only add items with a name
                    invoice.items.append(invoice_item)

    return invoice


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
        print("Could not seek to start of file.")
    pdf_bytes = file.file.read()
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        extract_invoice_pdf(str(file.filename), docs, pdf)
    return docs

def extract_invoice_pdf(filename: str, docs: List[Dict[str, Any]], pdf) -> None:
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



def parse_date_from_text(text: str) -> list[datetime.date]:
        candidates = []
        # common date patterns: 2023-12-06, 06.12.2023, 06/12/2023, 06-12-2023
        for m in re.findall(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", text):
            for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%y"):
                try:
                    d = datetime.strptime(m, fmt).date()
                    candidates.append(d)
                    break
                except Exception:
                    continue
        return candidates

def find_total_amount(text: str) -> float | None:
    m = re.search(r"(?i)(total|razem|suma|sum[^\s]*)[^\d\n\r]*([\d\.,]+)", text)
    if not m:
        # try any large-ish number on the page
        m2 = re.search(r"([0-9]{1,3}(?:[ ,.\u00A0]\d{3})*(?:[.,]\d{2})?)", text)
        if not m2:
            return None
        s = m2.group(1)
    else:
        s = m.group(2)
    s = s.replace("\u00A0", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

def docs_to_invoice(docs: list[dict]) -> Invoice:
    combined_text = "\n\n".join(d["text"] for d in docs)
    dates = parse_date_from_text(combined_text)
    invoice = Invoice()
    if dates:
        invoice.date_of_issue = dates[0]
        if len(dates) > 1:
            invoice.date_of_sale = dates[1]
    invoice.total_amount = find_total_amount(combined_text)
    # you can add more parsing: buyer/seller, items, currency, etc.
    return invoice



if __name__ == "__main__":
    pdf_docs = extract_invoice_text_from_path("C:\\Users\\Neko\\source\\repos\\InvoiceReader\\app\\services\\invoice.pdf")
    invoice_obj = docs_to_invoice(pdf_docs)
    print("Parsed Invoice:")
    print(invoice_obj)
    # for d in pdf_docs:
    #     page = d["metadata"]["page"]
    #     print(f"PAGE: {page}")
    #     print(d["text"], "...\n")
