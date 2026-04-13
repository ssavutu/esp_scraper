# Local Firecrawl (Docker)

This repo includes a local Firecrawl stack in `docker-compose.firecrawl.yml`.

## 1) Prepare env

```bash
cp .env.firecrawl.example .env.firecrawl
```

Update at least:

- `BULL_AUTH_KEY` (change from `CHANGEME`)
- For Ollama (no cloud API key):
  - `OLLAMA_BASE_URL=http://host.docker.internal:11434/api`
  - `MODEL_NAME=llama3.1:8b` (or your installed Ollama model)
  - `MODEL_EMBEDDING_NAME=nomic-embed-text`
  - Leave `OPENAI_API_KEY` unset

Make sure Ollama is running on your host and the models are pulled:

```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
ollama serve
```

## 2) Start Firecrawl

```bash
docker compose --env-file .env.firecrawl -f docker-compose.firecrawl.yml up -d
```

API will be available at:

- `http://localhost:3002`
- Optional Playwright service endpoint: `http://localhost:3000/scrape`

Queue admin UI:

- `http://localhost:3002/admin/<BULL_AUTH_KEY>/queues`

## 3) Quick health test

```bash
curl -X POST http://localhost:3002/v1/crawl \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://firecrawl.dev"}'
```

## 3.1) Optional Playwright service check

This checks the standalone Playwright microservice directly:

```bash
curl -X POST http://localhost:3000/scrape \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://firecrawl.dev"}'
```

## 4) Stop

```bash
docker compose --env-file .env.firecrawl -f docker-compose.firecrawl.yml down
```

To also remove db volume:

```bash
docker compose --env-file .env.firecrawl -f docker-compose.firecrawl.yml down -v
```
