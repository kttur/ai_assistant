FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        "python-telegram-bot>=21.6,<22" \
        "python-dotenv>=1.0.1,<2" \
        "openai>=1.55.0" \
        "anthropic>=0.39.0" \
        "httpx>=0.27.0,<1.0.0" \
        "psycopg[binary]>=3.2.0,<4"

COPY src ./src
COPY main.py ./

RUN pip install --no-cache-dir --no-deps .

CMD ["python", "-m", "ai_assistant"]
