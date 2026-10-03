FROM python:3.11-slim

WORKDIR /app

# Install system dependencies & Playwright Chromium with browser OS libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium

# Copy application source code
COPY . .

# Seed initial database & PDFs
RUN python -m mock_apps.seed

# Expose ports: 8000 (Web UI), 8001 (Vendor Portal), 8002 (Finance System)
EXPOSE 8000 8001 8002

CMD ["python", "-m", "mock_apps.run_servers"]
