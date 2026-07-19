FROM python:3.10-slim

# Install system dependencies required for OpenCV and exiftool
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    exiftool \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Install Python dependencies first (for better cache utilization)
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create directory for rembg weights so it doesn't download every time
ENV U2NET_HOME=/app/models

# Copy the rest of the application
COPY app/ /app/code/

# Create data directories
RUN mkdir -p /app/data /app/static/uploads /app/static/processed /app/models

# Set Environment variables
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1
ENV FLIR_DATA_DIR=/app/data
ENV FLIR_UPLOAD_DIR=/app/static/uploads
ENV FLIR_PROCESSED_DIR=/app/static/processed
ENV PYTHONPATH=/app/code

# Expose port
EXPOSE 5050

# Set working directory to the code folder
WORKDIR /app/code

# Command to run the server with Gunicorn (1 worker, 8 threads for concurrency)
CMD ["gunicorn", "--bind", "0.0.0.0:5050", "--workers", "1", "--threads", "8", "--timeout", "120", "app:app"]
