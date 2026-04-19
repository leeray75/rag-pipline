#!/usr/bin/env bash
set -euo pipefail

PHASE=7
COMMIT_MSG="feat(phase-$PHASE):"
ROOT="rag-pipeline"

echo "=== Rolling back Phase $PHASE ==="
echo "Phase: MCP Server, Observability, Polish & Production Hardening"
echo ""

if ! git rev-parse --is-inside-work-tree &>/dev/null; then echo "❌ Not inside a git repository."; exit 1; fi

PHASE_COMMITS=$(git log --oneline --grep="$COMMIT_MSG" --format="%H %s" 2>/dev/null || true)

if [ -z "$PHASE_COMMITS" ]; then
  echo "⚠️  No commits found. File-based rollback..."

  FILES_TO_REMOVE=(
    "$ROOT/apps/api/src/mcp/server.py"
    "$ROOT/apps/api/src/mcp/tool_handlers.py"
    "$ROOT/apps/api/src/mcp/sse_transport.py"
    "$ROOT/apps/api/src/mcp/__main__.py"
    "$ROOT/apps/api/src/auth/jwt_handler.py"
    "$ROOT/apps/api/src/auth/dependencies.py"
    "$ROOT/apps/api/src/auth/__init__.py"
    "$ROOT/apps/api/src/security/ssrf_prevention.py"
    "$ROOT/apps/api/src/security/rate_limiter.py"
    "$ROOT/apps/api/src/security/__init__.py"
    "$ROOT/apps/api/src/observability/tracing.py"
    "$ROOT/apps/api/src/observability/metrics.py"
    "$ROOT/apps/api/src/observability/logging_config.py"
    "$ROOT/apps/api/src/observability/sentry_init.py"
    "$ROOT/apps/api/src/observability/__init__.py"
    "$ROOT/infra/docker-compose.prod.yml"
    "$ROOT/infra/prometheus/prometheus.yml"
    "$ROOT/infra/tempo/tempo.yaml"
    "$ROOT/docs/README.md"
    "$ROOT/docs/MCP_TOOLS.md"
    "$ROOT/docs/API_REFERENCE.md"
    "$ROOT/docs/DEPLOYMENT.md"
  )

  DIRS_TO_REMOVE=(
    "$ROOT/apps/api/src/auth"
    "$ROOT/apps/api/src/security"
    "$ROOT/apps/api/src/observability"
    "$ROOT/infra/prometheus"
    "$ROOT/infra/tempo"
    "$ROOT/infra/grafana"
  )

  for file in "${FILES_TO_REMOVE[@]}"; do
    if [ -f "$file" ]; then rm -f "$file"; echo "  🗑️  Removed $file"; fi
  done
  for dir in "${DIRS_TO_REMOVE[@]}"; do
    if [ -d "$dir" ]; then rm -rf "$dir"; echo "  🗑️  Removed $dir/"; fi
  done

  echo ""; echo "✅ File-based rollback complete."; exit 0
fi

FIRST_PHASE_COMMIT=$(echo "$PHASE_COMMITS" | tail -1 | awk '{print $1}')
PRE_PHASE_COMMIT=$(git rev-parse "${FIRST_PHASE_COMMIT}^" 2>/dev/null || true)
if [ -z "$PRE_PHASE_COMMIT" ]; then echo "❌ Cannot find parent commit."; exit 1; fi

echo "Rolling back to: $(git log --oneline -1 "$PRE_PHASE_COMMIT")"
read -p "⚠️  Continue? [y/N] " -n 1 -r; echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then echo "Cancelled."; exit 0; fi

SAFETY_BRANCH="backup/pre-rollback-phase-$PHASE-$(date +%Y%m%d-%H%M%S)"
git branch "$SAFETY_BRANCH"
git reset --hard "$PRE_PHASE_COMMIT"
echo "✅ Phase $PHASE rolled back. Safety branch: $SAFETY_BRANCH"
