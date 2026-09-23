#!/usr/bin/env bash
# ==============================================================================
# Setup GCP Prerequisites for Social Story Agent
# Usage: ./scripts/setup_prereqs.sh [PROJECT_ID] [REGION]
# ==============================================================================

set -euo pipefail

# 1. Resolve Project ID
PROJECT_ID="${1:-${GOOGLE_CLOUD_PROJECT:-${PROJECT_ID:-}}}"
REGION="${2:-us-east1}"

if [ -z "${PROJECT_ID}" ]; then
  PROJECT_ID=$(gcloud config get-value project 2>/dev/null || true)
fi

if [ -z "${PROJECT_ID}" ] || [ "${PROJECT_ID}" = "(unset)" ]; then
  echo "❌ Error: Could not determine GCP Project ID."
  echo "Usage: ./scripts/setup_prereqs.sh <PROJECT_ID> [REGION]"
  echo "  Or set GOOGLE_CLOUD_PROJECT environment variable."
  exit 1
fi

echo "============================================================"
echo "🚀 Setting up Social Story Agent Prerequisites"
echo "  GCP Project ID : ${PROJECT_ID}"
echo "  Target Region  : ${REGION}"
echo "============================================================"

# Ensure gcloud is configured to target project
gcloud config set project "${PROJECT_ID}" --quiet

# 2. Enable Required GCP APIs
echo ""
echo "📦 1. Enabling required Google Cloud APIs..."
REQUIRED_APIS=(
  "aiplatform.googleapis.com"
  "storage.googleapis.com"
  "firestore.googleapis.com"
  "logging.googleapis.com"
  "secretmanager.googleapis.com"
  "cloudbuild.googleapis.com"
  "run.googleapis.com"
)

gcloud services enable "${REQUIRED_APIS[@]}" --project="${PROJECT_ID}"
echo "✅ APIs enabled successfully."

# 3. Create GCS Media Storage Bucket
BUCKET_NAME="social-story-media-${PROJECT_ID}"
echo ""
echo "🪣 2. Verifying Google Cloud Storage Media Bucket: gs://${BUCKET_NAME}"

if gcloud storage buckets describe "gs://${BUCKET_NAME}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "ℹ️  GCS Bucket 'gs://${BUCKET_NAME}' already exists."
else
  echo "🛠️  Creating GCS Bucket 'gs://${BUCKET_NAME}' in location '${REGION}'..."
  gcloud storage buckets create "gs://${BUCKET_NAME}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --uniform-bucket-level-access
  echo "✅ GCS Bucket created."
fi

# Configure Public Object Read Access for Media Serving
echo "🔑 Granting public object read access for media rendering..."
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
  --member="allUsers" \
  --role="roles/storage.objectViewer" >/dev/null 2>&1 || true

# Set CORS policy for web browser access
echo "🌐 Setting bucket CORS configuration..."
CORS_JSON=$(cat <<EOF
[
  {
    "origin": ["*"],
    "method": ["GET", "HEAD", "OPTIONS"],
    "responseHeader": ["Content-Type", "Access-Control-Allow-Origin"],
    "maxAgeSeconds": 3600
  }
]
EOF
)
TMP_CORS=$(mktemp)
echo "${CORS_JSON}" > "${TMP_CORS}"
gcloud storage buckets update "gs://${BUCKET_NAME}" --cors-file="${TMP_CORS}" >/dev/null 2>&1 || true
rm -f "${TMP_CORS}"
echo "✅ GCS Media Bucket configured."

# 4. Check/Initialize Cloud Firestore Database
echo ""
echo "🔥 3. Verifying Cloud Firestore database..."
if gcloud firestore databases describe --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "ℹ️  Cloud Firestore database is active."
else
  echo "🛠️  Initializing Cloud Firestore database (Native Mode) in location '${REGION}'..."
  gcloud firestore databases create \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --type=firestore-native || true
  echo "✅ Firestore database initialized."
fi

# 5. Service Account IAM Role Verification
echo ""
echo "🛡️ 4. Checking Service Account IAM roles..."
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)" 2>/dev/null || true)
if [ -n "${PROJECT_NUMBER}" ]; then
  AI_PLATFORM_SA="service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
  echo "  Agent Runtime Service Account: ${AI_PLATFORM_SA}"
  echo "  Granting Storage Object Admin & Datastore User roles if needed..."
  
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${AI_PLATFORM_SA}" \
    --role="roles/storage.objectAdmin" --quiet >/dev/null 2>&1 || true

  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${AI_PLATFORM_SA}" \
    --role="roles/datastore.user" --quiet >/dev/null 2>&1 || true

  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${AI_PLATFORM_SA}" \
    --role="roles/logging.logWriter" --quiet >/dev/null 2>&1 || true
fi

echo ""
echo "============================================================"
echo "🎉 Prerequisites setup complete for project: ${PROJECT_ID}"
echo "  Media Bucket : gs://${BUCKET_NAME}"
echo "  Firestore    : Active"
echo "  APIs Enabled : ${REQUIRED_APIS[*]}"
echo "============================================================"
