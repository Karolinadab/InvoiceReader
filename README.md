# Invoice Reader
Small app that reads PDF invoices, ingest documents to RAG, uses LLM to retrieve data to search/ summarize ionvoices.


## Instructions:
Run commands from main.py level in CMD:


### Create venv:
python -m venv venv
venv\\Scripts\\activate


### Install requirements:
pip install -r requirements.txt


### Run app:
uvicorn main:app --reload --host 127.0.0.1 --port 8000

### Navigate to:
http://127.0.0.1:8000/docs