from fastapi import FastAPI, File, UploadFile, HTTPException
import camelot
import tempfile
import os
import tabula
import pdfplumber
import pandas as pd

from app.services.upload_service import extract_invoice_text_from_file

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    pdf_docs = extract_invoice_text_from_file(file)
    for document in pdf_docs:
        page = document["metadata"]["page"]
        print(f"PAGE: {page}")
        print(document["text"], "...\n")
        
    return {"filename": file.filename, "content_type": file.content_type}

@app.get("/documents")
async def get_documents_info():
    return {"documents": []}



@app.post("/extract-invoice")
async def extract_invoice(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Save UploadFile to a temp PDF
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = tmp.name
        contents = await file.read()
        tmp.write(contents)

    try:
        # Extract tables (try lattice first for invoices with borders)
        tables = camelot.read_pdf(tmp_path, pages="1", flavor="lattice")

        if tables.n == 0:
            # fallback to stream (for borderless tables)
            tables = camelot.read_pdf(tmp_path, pages="1", flavor="stream")

        if tables.n == 0:
            return {"tables_found": 0, "tables": []}

        # Convert all tables to JSON-friendly format
        extracted = []
        for i, t in enumerate(tables):
            extracted.append({
                "table_index": i,
                "shape": t.df.shape,
                "data": t.df.to_dict(orient="records")  # list of row dicts
            })

        return {
            "tables_found": tables.n,
            "tables": extracted
        }

    finally:
        # Cleanup temp file
        os.remove(tmp_path)


@app.post("/extract-invoice-tabula")
async def extract_invoice_tabula(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Save UploadFile to a temp PDF (tabula reads from a file path)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = tmp.name
        tmp.write(await file.read())

    try:
        # Extract tables from first page (set pages="all" for multipage invoices)
        dfs = tabula.read_pdf(
            tmp_path,
            pages=1,
            multiple_tables=True,
            guess=True,          # let tabula detect table areas
            lattice=True         # try ruled-line tables (good for invoices)
            # stream=True        # alternative for borderless tables (use instead of lattice)
        )

        if not dfs:
            # Fallback: try stream mode if lattice found nothing
            dfs = tabula.read_pdf(
                tmp_path,
                pages=1,
                multiple_tables=True,
                guess=True,
                stream=True
            )

        if not dfs:
            return {"tables_found": 0, "tables": []}

        extracted = []
        for i, df in enumerate(dfs):
            extracted.append({
                "table_index": i,
                "shape": [int(df.shape[0]), int(df.shape[1])],
                "data": df.fillna("").to_dict(orient="records")  # JSON-friendly
            })

        return {"tables_found": len(dfs), "tables": extracted}

    finally:
        os.remove(tmp_path)


@app.post("/extract-invoice-plumber")
async def extract_invoice_plumber(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Save UploadFile to a temp PDF (pdfplumber reads from a file path)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = tmp.name
        tmp.write(await file.read())

    try:
        tables_out = []

        with pdfplumber.open(tmp_path) as pdf:
            # For multipage invoices, iterate: for page_index, page in enumerate(pdf.pages)
            page_index = 0
            page = pdf.pages[page_index]

            # Try to extract all tables found on the page
            tables = page.extract_tables()  # list[list[list[str|None]]]

            if not tables:
                return {"tables_found": 0, "tables": []}

            for i, table in enumerate(tables):
                # table is rows; first row is often header but not always
                # We'll return two representations:
                # 1) raw rows (always safe)
                # 2) best-effort dataframe (if it looks headered)
                raw_rows = [[cell if cell is not None else "" for cell in row] for row in table]

                df_payload = None
                if len(raw_rows) >= 2 and len(raw_rows[0]) == len(raw_rows[1]):
                    header = raw_rows[0]
                    data_rows = raw_rows[1:]
                    df = pd.DataFrame(data_rows, columns=header)
                    df_payload = {
                        "shape": [int(df.shape[0]), int(df.shape[1])],
                        "data": df.fillna("").to_dict(orient="records")
                    }

                tables_out.append({
                    "page": page_index + 1,
                    "table_index": i,
                    "raw": raw_rows,
                    "dataframe": df_payload
                })

        return {"tables_found": len(tables_out), "tables": tables_out}

    finally:
        os.remove(tmp_path)