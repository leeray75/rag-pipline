# Phase 6, Subtask 2 Summary Report — JSON Schemas + Database Models + Chunking Pipeline

**Date:** 2026-04-18  
**Status:** Complete  
**Subtask:** Phase 6, Subtask 2 — JSON Schemas + Database Models + Chunking Pipeline

---

## Files Created/Modified

| File Path | Action | Description |
|-----------|--------|-------------|
| `rag-pipeline/apps/api/src/schemas/chunk.py` | Created | Pydantic schemas for chunk documents: ChunkMetadata, ChunkDocument, ChunkStats, EmbedRequest, EmbedProgress |
| `rag-pipeline/apps/api/src/schemas/collection.py` | Created | Pydantic schemas for Qdrant collection metadata: CollectionInfo, CollectionStats |
| `rag-pipeline/apps/api/src/schemas/__init__.py` | Modified | Added exports for new schemas (ChunkDocument, ChunkMetadata, ChunkStats, EmbedRequest, EmbedProgress, CollectionInfo, CollectionStats) |
| `rag-pipeline/apps/api/src/models/chunk.py` | Created | SQLAlchemy models: ChunkRecord (staged chunks), VectorCollection (Qdrant tracking) |
| `rag-pipeline/apps/api/src/models/document.py` | Modified | Added `chunks` relationship linking to ChunkRecord |
| `rag-pipeline/apps/api/src/models/ingestion_job.py` | Modified | Added `chunks` relationship for job-chunk linkage |
| `rag-pipeline/apps/api/src/models/vector_collection.py` | Modified | Updated schema to match subtask specification with correct field names |
| `rag-pipeline/apps/api/src/models/__init__.py` | Modified | Added ChunkRecord and VectorCollection exports |
| `rag-pipeline/apps/api/alembic/versions/2026_04_18_1708_add_chunks_and_update_vector_collections.py` | Created | Alembic migration for chunks table and vector_collections schema update |
| `rag-pipeline/apps/api/src/ingest/chunking_pipeline.py` | Created | ChunkingPipeline service for end-to-end Markdown chunking and persistence |

---

## Key Decisions

1. **Foreign Key Reference Resolution**: The subtask spec used `ForeignKey("jobs.id")` but the actual table name is `ingestion_jobs`. The implementation correctly uses `ForeignKey("ingestion_jobs.id")`.

2. **VectorCollection Schema Alignment**: The existing `vector_collection.py` model had different field names (`qdrant_collection_name`, `chunk_count`, `embedded_at`). Updated to match subtask specification (`collection_name`, `vector_dimensions`, `vector_count`, `document_count`, `status`, `error_message`).

3. **Import Conflict Resolution**: The subtask specifies creating `VectorCollection` in `chunk.py`, but `vector_collection.py` already exists. The `__init__.py` now exports `VectorCollection` from `chunk.py`, resolving the naming conflict.

4. **Cascade Delete Behavior**: `ChunkRecord.document_id` uses `CASCADE` delete to remove chunks when a document is deleted. `ChunkRecord.job_id` and `VectorCollection.job_id` use `SET NULL` for job deletion.

5. **Model Structure**: Combined `ChunkRecord` and `VectorCollection` in `src/models/chunk.py` as specified in the subtask, rather than keeping `VectorCollection` in its own file.

---

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| `Text` import missing in `vector_collection.py` | Added `Text` to the SQLAlchemy imports |
| Duplicate `VectorCollection` class name | Modified `models/__init__.py` to import `VectorCollection` from `chunk.py`, removing the old `OldVectorCollection` reference |
| Foreign key table name mismatch | Corrected `ForeignKey("jobs.id")` to `ForeignKey("ingestion_jobs.id")` |
| MetaData conflict | Removed duplicate `VectorCollection` import from `__init__.py` |

---

## Dependencies for Next Subtask

The next subtask (Phase 6, Subtask 3) will need:

1. **ChunkRecord model** - For querying staged chunks pending embedding
2. **VectorCollection model** - For tracking Qdrant collection status
3. **ChunkingPipeline** - For chunking approved documents
4. **EmbedRequest/EmbedProgress schemas** - For embedding API endpoints
5. **ChunkDocument schema** - For JSON serialization of chunks

---

## Verification Results

| # | Criterion | Verification Command | Result |
|---|-----------|---------------------|--------|
| 1 | `from src.schemas.chunk import ChunkDocument, EmbedRequest` works | `docker run --rm rag-pipeline-api-test python -c "from src.schemas.chunk import ChunkDocument, EmbedRequest"` | ✅ Passed |
| 2 | `from src.schemas.collection import CollectionInfo, CollectionStats` works | `docker run --rm rag-pipeline-api-test python -c "from src.schemas.collection import CollectionInfo, CollectionStats"` | ✅ Passed |
| 3 | `from src.models.chunk import ChunkRecord, VectorCollection` works | `docker run --rm rag-pipeline-api-test python -c "from src.models.chunk import ChunkRecord, VectorCollection"` | ✅ Passed |
| 4 | `from src.ingest.chunking_pipeline import ChunkingPipeline` works | `docker run --rm rag-pipeline-api-test python -c "from src.ingest.chunking_pipeline import ChunkingPipeline"` | ✅ Passed |
| 5 | All schemas import via `from src.schemas import ...` | `docker run --rm rag-pipeline-api-test python -c "from src.schemas import ChunkDocument, CollectionInfo, ..."` | ✅ Passed |
| 6 | Model relationships configured correctly | `docker run --rm rag-pipeline-api-test python -c "from src.models import Document; print(Document.chunks)"` | ✅ Passed |

---

## Summary

All files from Tasks 4-6 have been created and verified:
- **Task 4 (Schemas)**: Chunk and Collection Pydantic schemas created and exported
- **Task 5 (Models)**: ChunkRecord and VectorCollection SQLAlchemy models created with proper relationships
- **Task 6 (Pipeline)**: ChunkingPipeline service implemented for end-to-end chunking

The Alembic migration is ready to be applied to the database using:
```bash
cd rag-pipeline/apps/api
alembic upgrade head
```

---

*Report generated by AI agent on 2026-04-18*
