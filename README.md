# SuperMemoryAI

A production-shaped memory service for AI apps.

## Run locally (zero config, fake models)
    pip install -r requirements.txt
    uvicorn app.api:app --reload
    # then: curl -H "x-api-key: dev-key-change-me" \
    #   -X POST localhost:8000/memories -H "Content-Type: application/json" \
    #   -d '{"container_tag":"u1","text":"I take metformin 500mg"}'

## Run tests
    python test_e2e.py

## Endpoints
- POST /memories  -> 202, queues ingestion (redact -> extract -> embed -> link)
- GET  /search    -> recall latest relevant facts (tenant-filtered)
- GET  /profile   -> cached profile (built by nightly job)
- POST /ask       -> full RAG: recall + LLM answer
- GET  /health    -> ALB health check

## Nightly jobs (EventBridge -> Lambda/ECS scheduled task)
    python -m app.jobs    # forget expired, decay unused, rebuild profiles

## Going to production
Set environment variables:
    FAKE_MODE=0
    DATABASE_URL=mysql+pymysql://user:pass@host/db
    VECTOR_BACKEND=opensearch
    OPENSEARCH_ENDPOINT=https://...
    AWS_REGION=us-east-1
    API_KEY=<from Secrets Manager>
Then uncomment the production extras in requirements.txt.

Swap points (all behind interfaces):
- LLM:        app/llm.py        FakeLLM -> BedrockLLM
- Embeddings: app/embeddings.py FakeEmbedder -> STEmbedder
- Vector idx: app/embeddings.py MemoryIndex -> OpenSearchIndex
- Queue:      app/api.py        BackgroundTasks -> SQS + worker service
