FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && playwright install --with-deps chromium
COPY . .
ENV PORT=8080 PYTHONUNBUFFERED=1
CMD ["sh", "-c", "waitress-serve --port=${PORT} app:app"]
