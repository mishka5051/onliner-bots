FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY event_search_bot ./event_search_bot

RUN pip install --no-cache-dir .

CMD ["event-search-bot"]
