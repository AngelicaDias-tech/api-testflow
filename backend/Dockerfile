FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV API_TESTFLOW_DATABASE_URL=sqlite:////data/api_testflow.db
ENV API_TESTFLOW_SECRET_KEY_FILE=/data/.secret_key
VOLUME ["/data"]

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
