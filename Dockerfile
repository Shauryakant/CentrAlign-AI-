FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for Playwright Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    libglib2.0-0 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

# Copy application source code
COPY . .

# Seed initial database & PDFs
RUN python -m mock_apps.seed

# Expose ports: 8000 (Web UI), 8001 (Vendor Portal), 8002 (Finance System)
EXPOSE 8000 8001 8002

CMD ["python", "-m", "mock_apps.run_servers"]
