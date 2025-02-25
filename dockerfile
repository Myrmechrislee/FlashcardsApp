FROM python:3.11

WORKDIR /app

COPY requirements.txt .

RUN pip3 install -r requirements.txt

COPY . .

EXPOSE 443

ENV FLASK_APP=server.py
ENV MONGO_URL="mongodb://mongodb:27017/flashcards"

ENTRYPOINT ["gunicorn", "server:app"]