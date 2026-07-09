FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY partnership_bot ./partnership_bot

RUN pip install --no-cache-dir .

CMD ["partnership-bot"]
