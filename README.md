
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
ollama pull qwen3-vl:4b
python manage.py migrate


python manage.py runserver

Терминал 2
python manage.py process_pdfs --watch


