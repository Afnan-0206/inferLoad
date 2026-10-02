FROM python:3.12-slim

WORKDIR /app

# Install minimal OS dependencies for matplotlib rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY results/ ./results/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

EXPOSE 8000

ENV PORT=8000
ENV HOST=0.0.0.0

CMD ["sh", "-c", "uvicorn inferload.web:app --host 0.0.0.0 --port ${PORT:-8000}"]
