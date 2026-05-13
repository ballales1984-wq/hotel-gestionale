FROM python:3.14-slim

# System deps
RUN apt-get update && apt-get install -y \
    curl build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY requirements.txt requirements_ai.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements_ai.txt

# App code
COPY . .

# Create data directories
RUN mkdir -p /app/data/uploads /app/data/duckdb

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
