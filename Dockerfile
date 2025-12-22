FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# HARD cache bust (forces new layer)
ARG CACHE_BUST=railway_2025_12_22_1230
RUN echo "CACHE_BUST=$CACHE_BUST"

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
