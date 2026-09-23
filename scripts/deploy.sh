#!/usr/bin/env bash
# ==============================================================================
# Unified Build & Deployment Script for Social Story Agent
# Usage: ./scripts/deploy.sh [PROJECT_ID] [REGION] [EXTRA_DEPLOY_FLAGS]
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"

cd "${PROJECT_ROOT}"

# 1. Resolve Project ID & Region
PROJECT_ID="${1:-${GOOGLE_CLOUD_PROJECT:-${PROJECT_ID:-}}}"
REGION="${2:-us-east1}"
shift 2 2>/dev/null || shift $# 2>/dev/null || true

if [ -z "${PROJECT_ID}" ]; then
  PROJECT_ID=$(gcloud config get-value project 2>/dev/null || true)
fi

if [ -z "${PROJECT_ID}" ] || [ "${PROJECT_ID}" = "(unset)" ]; then
  echo "❌ Error: Could not determine GCP Project ID."
  echo "Usage: ./scripts/deploy.sh <PROJECT_ID> [REGION] [EXTRA_FLAGS]"
  exit 1
fi

export GOOGLE_CLOUD_PROJECT="${PROJECT_ID}"
export PROJECT_ID="${PROJECT_ID}"

echo "============================================================"
echo "🚀 Starting Automated Pre-Deployment Validation & Build"
echo "  Project ID: ${PROJECT_ID}"
echo "  Region    : ${REGION}"
echo "============================================================"

# 2. Step 1: Run & Validate Prerequisites Script
echo ""
echo "🔍 [Step 1/3] Validating and setting up GCP prerequisites..."
if [ -f "${SCRIPT_DIR}/setup_prereqs.sh" ]; then
  bash "${SCRIPT_DIR}/setup_prereqs.sh" "${PROJECT_ID}" "${REGION}"
else
  echo "❌ Error: ${SCRIPT_DIR}/setup_prereqs.sh not found."
  exit 1
fi
echo "✅ Prerequisites validated successfully."

# 3. Step 2: Code Validation (Pytest Suite)
echo ""
echo "🧪 [Step 2/3] Running pre-build test validation (pytest)..."
if command -v uv >/dev/null 2>&1; then
  uv run pytest tests/unit tests/integration
else
  pytest tests/unit tests/integration
fi
echo "✅ Code validation passed."

# 4. Step 3: Trigger Rebuild & Deployment
echo ""
echo "📦 [Step 3/3] Building and deploying agent via agents-cli..."
agents-cli deploy \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --no-confirm-project \
  "$@"

echo ""
echo "============================================================"
echo "🎉 Deployment & Build completed successfully for ${PROJECT_ID}!"
echo "============================================================"
