FROM python:3.10-slim

WORKDIR /app

# copy root requirements.txt (THIS EXISTS)
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# copy entire repo
COPY . .

EXPOSE 8080

# start via root main.py forwarder
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
