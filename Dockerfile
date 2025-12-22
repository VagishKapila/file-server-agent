FROM python:3.10-slim

WORKDIR /app

ENV PYTHONPATH=/app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend /app/backend
COPY main.py /app/main.py

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
