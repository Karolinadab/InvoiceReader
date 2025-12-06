from fastapi import FastAPI, File, UploadFile

from app.services.upload_service import extract_invoice_text_from_file

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}

# upload
@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    pdf_docs = extract_invoice_text_from_file(file)
    for document in pdf_docs:
        page = document["metadata"]["page"]
        print(f"PAGE: {page}")
        print(document["text"], "...\n")
        
    # Process the uploaded file contents
    return {"filename": file.filename, "content_type": file.content_type}

# get all documents info
@app.get("/documents")
async def get_documents_info():
    # Retrieve and return information about all uploaded documents
    return {"documents": []}