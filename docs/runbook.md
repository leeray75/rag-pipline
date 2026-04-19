# Operations Runbook

## Startup

```bash
# Development
cd infra && docker compose up -d
cd apps/api && uvicorn src.main:app --reload
cd apps/web && pnpm dev

# Production
cd infra && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Common Issues

### Celery worker not processing tasks
1. Check Redis connectivity: `redis-cli ping`
2. Check worker logs: `docker compose logs celery-worker`
3. Restart: `docker compose restart celery-worker`

### Qdrant collection not queryable
1. Check collection exists: `curl http://localhost:6333/collections`
2. Verify vector count: `curl http://localhost:6333/collections/{name}`
3. Check embedding dimensions match (should be 384)

### Agent loop stuck (non-convergence)
1. Check max_rounds guard (default: 5)
2. Review agent traces in Grafana → Explore → Tempo (filter by `service.name=rag-pipeline-api`)
3. Manual override: `POST /api/v1/jobs/{id}/force-complete`

### FastEmbed model not loading
1. Check cache dir: `~/.cache/fastembed/` or `$FASTEMBED_CACHE_DIR`
2. Delete cache and re-download: `rm -rf ~/.cache/fastembed/`
3. Verify: `python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"`

### Database migration failed
1. Check current head: `alembic current`
2. View history: `alembic history`
3. Downgrade if needed: `alembic downgrade -1`
4. Fix migration and re-run: `alembic upgrade head`

### MCP endpoint not responding
1. Confirm the API is running: `curl http://localhost:8000/health`
2. Test the MCP endpoint directly:
   ```bash
   curl -X POST http://localhost:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
   ```
3. Check API logs for import errors in `src/mcp/`

### Investigating errors (open-source observability)
- **Structured logs**: Grafana → Explore → Loki → `{job="rag-pipeline-api"} | json | level="error"`
- **Error rate metric**: Grafana → Explore → Prometheus → `rate(rag_jobs_failed_total[5m])`
- **Distributed traces**: Grafana → Explore → Tempo → filter by `status=error`

## Manual Override Procedures

### Skip audit for a document
```sql
UPDATE documents SET status = 'approved' WHERE id = '<doc-id>';
```

### Force re-embedding
```sql
UPDATE chunks SET embedding_status = 'pending' WHERE job_id = '<job-id>';
```
Then trigger: `POST /api/v1/ingest/jobs/{id}/embed`

### Delete a Qdrant collection
```bash
curl -X DELETE http://localhost:6333/collections/{name}
```

## Backup & Recovery

### Qdrant snapshots
```bash
curl -X POST http://localhost:6333/collections/{name}/snapshots
```

### Postgres backup
```bash
docker compose exec postgres pg_dump -U postgres rag_pipeline > backup.sql
```
