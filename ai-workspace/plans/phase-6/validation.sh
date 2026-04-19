#!/usr/bin/env bash
set -euo pipefail

PHASE=6
ROOT="rag-pipeline"
ERRORS=0

echo "=== Phase $PHASE Validation ==="
echo "Validating: JSON Generation, Chunking & Vector Ingestion"
echo ""

check_file() {
  if [ -f "$1" ]; then echo "  ✅ $1"; else echo "  ❌ MISSING: $1"; ERRORS=$((ERRORS + 1)); fi
}

echo "── 1. Source files ──"
check_file "$ROOT/apps/api/src/ingest/chunker.py"
check_file "$ROOT/apps/api/src/ingest/chunking_pipeline.py"
check_file "$ROOT/apps/api/src/ingest/qdrant_ingest.py"
check_file "$ROOT/apps/api/src/embeddings/fastembed_service.py"
check_file "$ROOT/apps/api/src/embeddings/config.py"
check_file "$ROOT/apps/api/src/schemas/chunk.py"
check_file "$ROOT/apps/api/src/schemas/collection.py"
check_file "$ROOT/apps/api/src/models/chunk.py"
check_file "$ROOT/apps/api/src/workers/ingest_tasks.py"
check_file "$ROOT/apps/api/src/routers/ingest.py"
echo ""

echo "── 2. Frontend files ──"
check_file "$ROOT/apps/web/src/store/ingestApi.ts"
check_file "$ROOT/apps/web/src/features/ingest/ChunkBrowser.tsx"
echo ""

echo "── 3. Python import checks ──"
PYTHON=""
if command -v python3 &>/dev/null; then PYTHON=python3;
elif command -v python &>/dev/null; then PYTHON=python; fi

if [ -n "$PYTHON" ] && [ -d "$ROOT/apps/api" ]; then
  pushd "$ROOT/apps/api" > /dev/null

  for module in \
    "src.ingest.chunker" \
    "src.ingest.chunking_pipeline" \
    "src.ingest.qdrant_ingest" \
    "src.embeddings.fastembed_service" \
    "src.embeddings.config" \
    "src.schemas.chunk" \
    "src.schemas.collection" \
    "src.models.chunk" \
    "src.workers.ingest_tasks" \
    "src.routers.ingest"; do
    if $PYTHON -c "import $module" 2>/dev/null; then
      echo "  ✅ import $module"
    else
      echo "  ❌ FAILED: import $module"; ERRORS=$((ERRORS + 1))
    fi
  done

  echo ""
  echo "── 4. Export checks ──"
  if $PYTHON -c "from src.ingest.chunker import Chunk, MarkdownChunker" 2>/dev/null; then
    echo "  ✅ chunker exports"
  else
    echo "  ❌ FAILED: chunker exports"; ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.embeddings.fastembed_service import FastEmbedService, MODEL_CONFIGS" 2>/dev/null; then
    echo "  ✅ fastembed_service exports"
  else
    echo "  ❌ FAILED: fastembed_service exports"; ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.ingest.qdrant_ingest import QdrantIngestService" 2>/dev/null; then
    echo "  ✅ qdrant_ingest exports"
  else
    echo "  ❌ FAILED: qdrant_ingest exports"; ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.schemas.chunk import ChunkDocument, ChunkMetadata, ChunkStats, EmbedRequest, EmbedProgress" 2>/dev/null; then
    echo "  ✅ chunk schema exports"
  else
    echo "  ❌ FAILED: chunk schema exports"; ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.schemas.collection import CollectionInfo, CollectionStats" 2>/dev/null; then
    echo "  ✅ collection schema exports"
  else
    echo "  ❌ FAILED: collection schema exports"; ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.models.chunk import ChunkRecord" 2>/dev/null; then
    echo "  ✅ chunk model exports"
  else
    echo "  ❌ FAILED: chunk model exports"; ERRORS=$((ERRORS + 1))
  fi

  # Verify FastEmbed model loads (may take time on first run)
  echo ""
  echo "── 5. FastEmbed model check ──"
  if $PYTHON -c "
from fastembed import TextEmbedding
model = TextEmbedding('BAAI/bge-small-en-v1.5')
embeddings = list(model.embed(['test']))
assert len(embeddings[0]) == 384, f'Expected 384 dims, got {len(embeddings[0])}'
print('  ✅ FastEmbed BAAI/bge-small-en-v1.5 produces 384-dim vectors')
" 2>/dev/null; then
    :
  else
    echo "  ⚠️  FastEmbed model check failed (may need download)"
  fi

  popd > /dev/null
fi
echo ""

echo "── 6. Type checking (mypy) ──"
if [ -n "$PYTHON" ] && command -v mypy &>/dev/null && [ -d "$ROOT/apps/api" ]; then
  pushd "$ROOT/apps/api" > /dev/null
  if mypy src/ingest/ src/embeddings/ src/schemas/chunk.py src/schemas/collection.py src/models/chunk.py --ignore-missing-imports --no-error-summary 2>/dev/null; then
    echo "  ✅ mypy passed"
  else
    echo "  ❌ mypy found type errors"; ERRORS=$((ERRORS + 1))
  fi
  popd > /dev/null
else
  echo "  ⚠️  mypy not available — skipping"
fi
echo ""

echo "── 7. TypeScript compilation ──"
if command -v npx &>/dev/null && [ -d "$ROOT/apps/web" ]; then
  pushd "$ROOT/apps/web" > /dev/null
  if npx tsc --noEmit 2>/dev/null; then
    echo "  ✅ TypeScript compilation passed"
  else
    echo "  ❌ TypeScript compilation failed"; ERRORS=$((ERRORS + 1))
  fi
  popd > /dev/null
else
  echo "  ⚠️  npx not available — skipping"
fi
echo ""

echo "── 8. Router registration ──"
if [ -f "$ROOT/apps/api/src/main.py" ]; then
  if grep -q "ingest" "$ROOT/apps/api/src/main.py"; then
    echo "  ✅ ingest router registered in main.py"
  else
    echo "  ❌ ingest router not registered in main.py"; ERRORS=$((ERRORS + 1))
  fi
fi
echo ""

echo "════════════════════════════════════════"
if [ $ERRORS -eq 0 ]; then echo "✅ Phase $PHASE validation PASSED"; exit 0
else echo "❌ Phase $PHASE validation FAILED — $ERRORS error(s)"; exit 1; fi
