FROM python:3.12-slim

WORKDIR /app

# Install API deps
COPY api/requirements.txt /app/api/requirements.txt
RUN pip install --no-cache-dir -r /app/api/requirements.txt

# Copy preprocessor and API
COPY preprocess.py /app/preprocess.py
COPY api/main.py /app/api/main.py

ENV MANA_VAULT_BASE=/app

EXPOSE 8200

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8200"]
