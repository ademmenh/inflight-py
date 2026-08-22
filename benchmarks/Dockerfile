FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY inflight ./inflight

RUN pip install --no-cache-dir -e ".[bench]"

COPY benchmarks ./benchmarks

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "benchmarks.bench"]
