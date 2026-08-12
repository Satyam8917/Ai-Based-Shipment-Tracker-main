# Dockerfile for AI Shipment Delay Predictor

FROM python:3.11-slim

# Set workdir
WORKDIR /app

# Install build deps (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY Requirements.txt ./
RUN pip install --no-cache-dir -r Requirements.txt

# Copy the application
COPY . .

# Create data directory (optional)
RUN mkdir -p /app/data

# Expose port
EXPOSE 5001

# Default command
CMD ["python", "app.py"]
