FROM python:3.11-slim

# Install Tesseract OCR with Spanish language pack
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app
ENV TESSERACT_PATH=/usr/bin/tesseract
ENV OCR_LANGUAGE=spa
ENV CONFIDENCE_THRESHOLD=0.7

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
