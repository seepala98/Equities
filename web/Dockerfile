FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    ca-certificates \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# No browser needed: we will fetch data with yfinance

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . /app

RUN chmod +x /app/entrypoint.py

ENTRYPOINT ["python", "/app/entrypoint.py"]
