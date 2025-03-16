FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y curl

COPY time_sync_app.py .
COPY cli.py .

RUN chmod +x cli.py
RUN chmod +x time_sync_app.py

ENV FLASK_APP=time_sync_app.py
ENV FLASK_ENV=development

CMD ["python", "time_sync_app.py"]