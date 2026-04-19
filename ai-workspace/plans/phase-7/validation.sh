#!/usr/bin/env bash
set -euo pipefail

PHASE=7
ROOT="rag-pipeline"
ERRORS=0

echo "=== Phase $PHASE Validation ==="
echo "Validating: MCP Server, Observability, Polish & Production Hardening"
echo ""

check_file() {
  if [ -f "$1" ]; then echo "  ✅ $1"; else echo "  ❌ MISSING: $1"; ERRORS=$((ERRORS + 1)); fi
}

echo "── 1. MCP Server files ──"
check_file "$ROOT/apps/api/src/mcp/server.py"
check_file "$ROOT/apps/api/src/mcp/tool_handlers.py"
check_file "$ROOT/apps/api/src/mcp/sse_transport.py"
check_file "$ROOT/apps/api/src/mcp/__main__.py"
echo ""

echo "── 2. Auth files ──"
check_file "$ROOT/apps/api/src/auth/__init__.py"
check_file "$ROOT/apps/api/src/auth/jwt_handler.py"
check_file "$ROOT/apps/api/src/auth/dependencies.py"
echo ""

echo "── 3. Security files ──"
check_file "$ROOT/apps/api/src/security/__init__.py"
check_file "$ROOT/apps/api/src/security/ssrf_prevention.py"
check_file "$ROOT/apps/api/src/security/rate_limiter.py"
echo ""

echo "── 4. Observability files ──"
check_file "$ROOT/apps/api/src/observability/__init__.py"
check_file "$ROOT/apps/api/src/observability/tracing.py"
check_file "$ROOT/apps/api/src/observability/metrics.py"
check_file "$ROOT/apps/api/src/observability/logging_config.py"
check_file "$ROOT/apps/api/src/observability/sentry_init.py"
echo ""

echo "── 5. Infrastructure files ──"
check_file "$ROOT/infra/docker-compose.prod.yml"
check_file "$ROOT/infra/prometheus/prometheus.yml"
check_file "$ROOT/infra/tempo/tempo.yaml"
check_file "$ROOT/infra/grafana/provisioning/datasources/datasources.yml"
check_file "$ROOT/infra/grafana/provisioning/dashboards/dashboards.yml"
echo ""

echo "── 6. Documentation files ──"
check_file "$ROOT/docs/README.md"
check_file "$ROOT/docs/MCP_TOOLS.md"
check_file "$ROOT/docs/API_REFERENCE.md"
check_file "$ROOT/docs/DEPLOYMENT.md"
echo ""

echo "── 7. Python import checks ──"
PYTHON=""
if command -v python3 &>/dev/null; then PYTHON=python3;
elif command -v python &>/dev/null; then PYTHON=python; fi

if [ -n "$PYTHON" ] && [ -d "$ROOT/apps/api" ]; then
  pushd "$ROOT/apps/api" > /dev/null

  for module in \
    "src.mcp.server" \
    "src.mcp.tool_handlers" \
    "src.mcp.sse_transport" \
    "src.auth.jwt_handler" \
    "src.auth.dependencies" \
    "src.security.ssrf_prevention" \
    "src.security.rate_limiter" \
    "src.observability.tracing" \
    "src.observability.metrics" \
    "src.observability.logging_config" \
    "src.observability.sentry_init"; do
    if $PYTHON -c "import $module" 2>/dev/null; then
      echo "  ✅ import $module"
    else
      echo "  ❌ FAILED: import $module"; ERRORS=$((ERRORS + 1))
    fi
  done

  echo ""
  echo "── 8. Export checks ──"

  # MCP exports
  if $PYTHON -c "from src.mcp.server import mcp, list_tools" 2>/dev/null; then
    echo "  ✅ MCP server exports"
  else
    echo "  ❌ FAILED: MCP server exports"; ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.mcp.tool_handlers import call_tool" 2>/dev/null; then
    echo "  ✅ MCP tool_handlers exports"
  else
    echo "  ❌ FAILED: MCP tool_handlers exports"; ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.mcp.sse_transport import router, sse_transport" 2>/dev/null; then
    echo "  ✅ MCP sse_transport exports"
  else
    echo "  ❌ FAILED: MCP sse_transport exports"; ERRORS=$((ERRORS + 1))
  fi

  # Auth exports
  if $PYTHON -c "from src.auth.jwt_handler import create_access_token, verify_token" 2>/dev/null; then
    echo "  ✅ JWT handler exports"
  else
    echo "  ❌ FAILED: JWT handler exports"; ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.auth.dependencies import get_current_user" 2>/dev/null; then
    echo "  ✅ Auth dependencies exports"
  else
    echo "  ❌ FAILED: Auth dependencies exports"; ERRORS=$((ERRORS + 1))
  fi

  # Security exports
  if $PYTHON -c "from src.security.ssrf_prevention import validate_url, safe_fetch" 2>/dev/null; then
    echo "  ✅ SSRF prevention exports"
  else
    echo "  ❌ FAILED: SSRF prevention exports"; ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.security.rate_limiter import limiter" 2>/dev/null; then
    echo "  ✅ Rate limiter exports"
  else
    echo "  ❌ FAILED: Rate limiter exports"; ERRORS=$((ERRORS + 1))
  fi

  # Observability exports
  if $PYTHON -c "from src.observability.tracing import init_tracing" 2>/dev/null; then
    echo "  ✅ Tracing exports"
  else
    echo "  ❌ FAILED: Tracing exports"; ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.observability.metrics import init_metrics" 2>/dev/null; then
    echo "  ✅ Metrics exports"
  else
    echo "  ❌ FAILED: Metrics exports"; ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.observability.logging_config import configure_logging" 2>/dev/null; then
    echo "  ✅ Logging config exports"
  else
    echo "  ❌ FAILED: Logging config exports"; ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.observability.sentry_init import init_sentry" 2>/dev/null; then
    echo "  ✅ Sentry init exports"
  else
    echo "  ❌ FAILED: Sentry init exports"; ERRORS=$((ERRORS + 1))
  fi

  popd > /dev/null
fi
echo ""

# ─── MCP tool count verification ─────────────────────────────────
echo "── 9. MCP tool count ──"
if [ -n "$PYTHON" ] && [ -d "$ROOT/apps/api" ]; then
  pushd "$ROOT/apps/api" > /dev/null
  TOOL_COUNT=$($PYTHON -c "
import asyncio
from src.mcp.server import list_tools
tools = asyncio.run(list_tools())
print(len(tools))
" 2>/dev/null || echo "0")
  if [ "$TOOL_COUNT" -ge 7 ] 2>/dev/null; then
    echo "  ✅ MCP server exposes $TOOL_COUNT tools (expected ≥7)"
  else
    echo "  ❌ MCP server exposes $TOOL_COUNT tools (expected ≥7)"; ERRORS=$((ERRORS + 1))
  fi
  popd > /dev/null
fi
echo ""

echo "── 10. Type checking (mypy) ──"
if [ -n "$PYTHON" ] && command -v mypy &>/dev/null && [ -d "$ROOT/apps/api" ]; then
  pushd "$ROOT/apps/api" > /dev/null
  if mypy src/mcp/ src/auth/ src/security/ src/observability/ --ignore-missing-imports --no-error-summary 2>/dev/null; then
    echo "  ✅ mypy passed"
  else
    echo "  ❌ mypy found type errors"; ERRORS=$((ERRORS + 1))
  fi
  popd > /dev/null
else
  echo "  ⚠️  mypy not available — skipping"
fi
echo ""

echo "── 11. Docker Compose prod validation ──"
if command -v docker &>/dev/null && [ -f "$ROOT/infra/docker-compose.prod.yml" ]; then
  pushd "$ROOT/infra" > /dev/null
  if docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet 2>/dev/null; then
    echo "  ✅ Production Docker Compose config is valid"
  else
    echo "  ❌ Production Docker Compose config is invalid"; ERRORS=$((ERRORS + 1))
  fi
  popd > /dev/null
else
  echo "  ⚠️  Docker not available — skipping compose validation"
fi
echo ""

echo "════════════════════════════════════════"
if [ $ERRORS -eq 0 ]; then echo "✅ Phase $PHASE validation PASSED"; exit 0
else echo "❌ Phase $PHASE validation FAILED — $ERRORS error(s)"; exit 1; fi
