FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY AIservices/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY AIservices/ ./AIservices/

EXPOSE 8001

ENV PYTHONPATH=/app
ENV REDIS_URL=redis://redis:6379/0

CMD ["uvicorn", "AIservices.main:app", "--host", "0.0.0.0", "--port", "8001"]
