# Small official Python base image.
FROM python:3.12-slim

# Don't write .pyc files; send logs straight out so docker logs shows them.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies FIRST, as their own layer. Docker caches this layer, so
# editing application code does not reinstall packages on every rebuild.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Then copy the application code.
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
