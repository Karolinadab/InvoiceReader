from fastapi import FastAPI, File, UploadFile

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}

# upload
@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    contents = await file.read()
    # Process the uploaded file contents
    return {"filename": file.filename, "content_type": file.content_type}

# get all documents info
@app.get("/documents")
async def get_documents_info():
    # Retrieve and return information about all uploaded documents
    return {"documents": []}