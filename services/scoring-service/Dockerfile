FROM python:3.11-slim

WORKDIR /app

RUN useradd -m appuser

COPY services/scoring-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY libs /app/libs
COPY services/scoring-service/app /app/app

ENV PYTHONPATH=/app
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
