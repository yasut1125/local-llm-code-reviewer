# Cloud Run LLM Code Reviewer

An automated, privacy-focused, self-hosted AI Code Reviewer for **GitHub Pull Requests** and **GitLab Merge Requests**. Powered by **Ollama** running on **GCP Cloud Run with NVIDIA L4 GPU**.

---

## Key Features

- **Privately Self-Hosted LLM**: Runs fully isolated inside your own GCP Cloud Run instance using Ollama (`qwen2.5-coder:14b`). Code diffs are never sent to third-party APIs (e.g., OpenAI/Gemini).
- **Cost Optimized**: Leverages Cloud Run with `min-instances: 0` (scale-to-zero). GPU resources are allocated only when triggered by Webhooks or command comments.
- **Dual Platform Support**: Seamlessly handles both **GitHub Pull Requests** and **GitLab Merge Requests** via environment configuration (`PLATFORM`).
- **Dynamic Rule Management**: Fetches system prompts/review guidelines dynamically from **Google Cloud Storage (GCS)** without requiring image rebuilds.
- **On-Demand & Event Triggers**: Automatically reviews newly opened/updated PRs/MRs, or triggers on demand via `/review` comment commands.
- **Enterprise-Grade Security**: Uses **Google Secret Manager** for access tokens/secrets and verifies HMAC SHA-256 Webhook signatures.
- **Ultra-Fast Builds**: Managed using **`uv`** for reproducible, fast Python dependency lockfiles.

---

## Architecture Overview

```text
┌──────────────────────────────┐
│  GitHub / GitLab Repository  │
└──────────────┬───────────────┘
               │ 1. Webhook (PR/MR event or /review comment)
               ▼
┌──────────────────────────────┐
│       GCP Cloud Run          │
│  ┌────────────────────────┐  │ 2. Fetch Prompt Rules
│  │ FastAPI App            ├──┼────────────────────────► [ GCS Bucket ]
│  └───────────┬────────────┘  │
│              │               │ 3. Run Inference
│              ▼               │
│  ┌────────────────────────┐  │
│  │ Ollama (NVIDIA L4 GPU) │  │
│  └────────────────────────┘  │
└──────────────┬───────────────┘
               │ 4. Post Review Comment
               ▼
┌──────────────────────────────┐
│  GitHub / GitLab Repository  │
└──────────────────────────────┘

```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
