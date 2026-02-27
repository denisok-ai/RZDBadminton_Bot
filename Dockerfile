FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создать директории для персистентных данных (если не примонтированы снаружи)
RUN mkdir -p data logs

CMD ["python3", "bot.py"]
