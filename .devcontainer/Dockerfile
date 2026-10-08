# Dev container image, kept separate from the app's production Dockerfile.
# Provides the same Ollama runtime plus tooling useful for local development
# (git, Google Cloud SDK) that the production image doesn't need.
FROM ollama/ollama:latest

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    git \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Google Cloud SDK (gcloud, gsutil) for local auth and interacting with GCP
# resources (Artifact Registry, GCS, Cloud Run, Secret Manager, etc.).
RUN curl -sSL https://sdk.cloud.google.com | bash -s -- --disable-prompts --install-dir=/usr/local \
    && ln -s /usr/local/google-cloud-sdk/bin/gcloud /usr/local/bin/gcloud \
    && ln -s /usr/local/google-cloud-sdk/bin/gsutil /usr/local/bin/gsutil
ENV PATH="/usr/local/google-cloud-sdk/bin:${PATH}"

WORKDIR /app
