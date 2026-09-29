# PolarSync AI - Dockerfile for Laptop / Raspberry Pi Edge Node
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Generate 8760h polar baseline data if not present
RUN python backend/data_generator.py

EXPOSE 8501 8000

# Start both FastAPI ingestion backend and Streamlit dashboard
CMD ["sh", "-c", "python -m uvicorn backend.api.server:app --host 0.0.0.0 --port 8000 & python -m streamlit run frontend/app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true"]
