#!/usr/bin/env bash
set -euo pipefail

PHASE=2
ROOT="rag-pipeline"
ERRORS=0

echo "=== Phase $PHASE Validation ==="
echo "Validating: URL Ingestion, Crawling & HTML→Markdown Conversion"
echo ""

# ─── Helper functions ───────────────────────────────────────────────
check_file() {
  if [ -f "$1" ]; then echo "  ✅ $1"; else echo "  ❌ MISSING: $1"; ERRORS=$((ERRORS + 1)); fi
}

# ─── 1. Check files exist ─────────────────────────────────────────
echo "── 1. Source files ──"
check_file "$ROOT/apps/api/src/crawlers/fetcher.py"
check_file "$ROOT/apps/api/src/crawlers/link_discovery.py"
check_file "$ROOT/apps/api/src/converters/markdown_converter.py"
check_file "$ROOT/apps/api/src/workers/crawl_tasks.py"
check_file "$ROOT/apps/api/src/routers/jobs.py"
check_file "$ROOT/apps/api/src/routers/websocket.py"
echo ""

echo "── 2. Test files ──"
check_file "$ROOT/apps/api/tests/test_converter.py"
check_file "$ROOT/apps/api/tests/test_link_discovery.py"
echo ""

echo "── 3. Frontend files ──"
check_file "$ROOT/apps/web/src/store/api/jobs-api.ts"
check_file "$ROOT/apps/web/src/app/ingestion/page.tsx"
check_file "$ROOT/apps/web/src/features/staging/staging-browser.tsx"
check_file "$ROOT/apps/web/src/hooks/use-job-progress.ts"
echo ""

# ─── 2. Check Python imports ──────────────────────────────────────
echo "── 4. Python import checks ──"
PYTHON=""
if command -v python3 &>/dev/null; then PYTHON=python3;
elif command -v python &>/dev/null; then PYTHON=python; fi

if [ -n "$PYTHON" ] && [ -d "$ROOT/apps/api" ]; then
  pushd "$ROOT/apps/api" > /dev/null

  for module in \
    "src.crawlers.fetcher" \
    "src.crawlers.link_discovery" \
    "src.converters.markdown_converter" \
    "src.workers.crawl_tasks" \
    "src.routers.jobs" \
    "src.routers.websocket"; do
    if $PYTHON -c "import $module" 2>/dev/null; then
      echo "  ✅ import $module"
    else
      echo "  ❌ FAILED: import $module"
      ERRORS=$((ERRORS + 1))
    fi
  done

  # Check specific exports
  echo ""
  echo "── 5. Export checks ──"
  if $PYTHON -c "from src.crawlers.fetcher import FetchMode, FetchResult, fetch_url, fetch_static, fetch_with_browser" 2>/dev/null; then
    echo "  ✅ fetcher exports"
  else
    echo "  ❌ FAILED: fetcher exports"
    ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.crawlers.link_discovery import DiscoveredLink, extract_links_with_selectors, discover_doc_links" 2>/dev/null; then
    echo "  ✅ link_discovery exports"
  else
    echo "  ❌ FAILED: link_discovery exports"
    ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.converters.markdown_converter import ConversionResult, convert_html_to_markdown" 2>/dev/null; then
    echo "  ✅ markdown_converter exports"
  else
    echo "  ❌ FAILED: markdown_converter exports"
    ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.workers.crawl_tasks import start_crawl_pipeline, fetch_seed_url, discover_links, fetch_and_convert_page, finalize_crawl" 2>/dev/null; then
    echo "  ✅ crawl_tasks exports"
  else
    echo "  ❌ FAILED: crawl_tasks exports"
    ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.routers.websocket import ConnectionManager, manager" 2>/dev/null; then
    echo "  ✅ websocket exports"
  else
    echo "  ❌ FAILED: websocket exports"
    ERRORS=$((ERRORS + 1))
  fi

  popd > /dev/null
else
  echo "  ⚠️  Python not found — skipping import checks"
fi
echo ""

# ─── 3. Type checking ─────────────────────────────────────────────
echo "── 6. Type checking (mypy) ──"
if [ -n "$PYTHON" ] && command -v mypy &>/dev/null && [ -d "$ROOT/apps/api" ]; then
  pushd "$ROOT/apps/api" > /dev/null
  if mypy src/crawlers/ src/converters/ src/routers/jobs.py src/routers/websocket.py --ignore-missing-imports --no-error-summary 2>/dev/null; then
    echo "  ✅ mypy passed"
  else
    echo "  ❌ mypy found type errors"
    ERRORS=$((ERRORS + 1))
  fi
  popd > /dev/null
else
  echo "  ⚠️  mypy not available — skipping"
fi
echo ""

# ─── 4. TypeScript compilation ────────────────────────────────────
echo "── 7. TypeScript compilation ──"
if command -v npx &>/dev/null && [ -d "$ROOT/apps/web" ]; then
  pushd "$ROOT/apps/web" > /dev/null
  if npx tsc --noEmit 2>/dev/null; then
    echo "  ✅ TypeScript compilation passed"
  else
    echo "  ❌ TypeScript compilation failed"
    ERRORS=$((ERRORS + 1))
  fi
  popd > /dev/null
else
  echo "  ⚠️  npx not available — skipping"
fi
echo ""

# ─── 5. Run tests ─────────────────────────────────────────────────
echo "── 8. Run Phase 2 tests ──"
if [ -n "$PYTHON" ] && command -v pytest &>/dev/null && [ -d "$ROOT/apps/api" ]; then
  pushd "$ROOT/apps/api" > /dev/null
  if pytest tests/test_converter.py tests/test_link_discovery.py -v --tb=short 2>/dev/null; then
    echo "  ✅ Tests passed"
  else
    echo "  ❌ Tests failed"
    ERRORS=$((ERRORS + 1))
  fi
  popd > /dev/null
else
  echo "  ⚠️  pytest not available — skipping"
fi
echo ""

# ─── 6. Check main.py router registration ────────────────────────
echo "── 9. Router registration check ──"
if [ -f "$ROOT/apps/api/src/main.py" ]; then
  if grep -q "jobs.router" "$ROOT/apps/api/src/main.py" && grep -q "websocket.router" "$ROOT/apps/api/src/main.py"; then
    echo "  ✅ jobs and websocket routers registered in main.py"
  else
    echo "  ❌ Routers not registered in main.py"
    ERRORS=$((ERRORS + 1))
  fi
fi
echo ""

# ─── Summary ──────────────────────────────────────────────────────
echo "════════════════════════════════════════"
if [ $ERRORS -eq 0 ]; then
  echo "✅ Phase $PHASE validation PASSED"
  exit 0
else
  echo "❌ Phase $PHASE validation FAILED — $ERRORS error(s)"
  exit 1
fi
