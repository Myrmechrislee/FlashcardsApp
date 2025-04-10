FROM python:3.11

WORKDIR /app

EXPOSE 8080

ENV FLASK_APP=server.py
ENV MONGO_URL="mongodb://mongodb:27017/flashcards"

ENTRYPOINT ["gunicorn", "server:app"]

COPY requirements.txt .

RUN pip3 install -r requirements.txt

COPY website/static website/static

COPY website/templates website/templates

COPY website/*.py website/

COPY *.py .