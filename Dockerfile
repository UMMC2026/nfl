FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

# Copy application
COPY ufa/ ./ufa/
COPY engine/ ./engine/
COPY output/ ./output/

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Expose port
EXPOSE 8000

# Run both API and Telegram bot
CMD ["sh", "-c", "python -m ufa.services.telegram_simple & uvicorn ufa.api.main:app --host 0.0.0.0 --port $PORT"]
