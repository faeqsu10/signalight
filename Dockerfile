# Stage 1: Install dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /install /usr/local

COPY config.py main.py ./
COPY signals/ signals/
COPY data/ data/
COPY bot/ bot/
COPY trading/ trading/
COPY scanner/ scanner/
COPY storage/ storage/
COPY infra/ infra/
COPY backtest/ backtest/

CMD ["python3", "main.py"]
