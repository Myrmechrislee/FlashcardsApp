FROM python:3.11

WORKDIR /app

COPY requirements.txt .

RUN pip3 install -r requirements.txt

COPY . .

EXPOSE 80

ENV FLASK_APP=server.py

ENTRYPOINT ["gunicorn", "server:app"]