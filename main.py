import os
import httpx
import hmac
import hashlib
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Header
from google.cloud import storage

app = FastAPI()

# Setting for platform ("github" or "gitlab")
PLATFORM = os.getenv("PLATFORM", "github").lower()

# Common settings
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
GCS_RULE_FILE_PATH = os.getenv("GCS_RULE_FILE_PATH")

# GitHub Settings
GITHUB_URL = os.getenv("GITHUB_URL", "https://api.github.com")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# GitLab Settings
GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.com")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

def verify_github_signature(payload_body: bytes, signature_header: str):
    """Verify GitHub webhook request signatures"""
    if not WEBHOOK_SECRET:
        return True  # if skip to verify signatures for dev only

    if not signature_header:
        raise HTTPException(status_code=401, detail="Signature header missing")

    # caluculate HMAC-SHA256
    secret_bytes = WEBHOOK_SECRET.encode('utf-8')
    expected_signature = "sha256=" + hmac.new(secret_bytes, payload_body, hashlib.sha256).hexdigest()

    # Use hmac.compare_digest to protect from timing attack
    if not hmac.compare_digest(expected_signature, signature_header):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
def fetch_prompt_from_gcs() -> str:
    """Get Rules for review from GCS"""
    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(GCS_RULE_FILE_PATH)
    return blob.download_as_text(encoding="utf-8")


async def get_ollama_review(diff_text: str) -> str:
    """Send a difference to Ollama (localhost:11434) and get the review results"""
    system_instruction = fetch_prompt_from_gcs()
    async with httpx.AsyncClient(timeout=300.0) as client:
        ollama_resp = await client.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "qwen2.5-coder:14b",
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": f"以下のコード変更差分をレビューしてください:\n\n{diff_text}"}
                ],
                "stream": False
            }
        )
        return ollama_resp.json()["message"]["content"]


# ==========================================
# GitHub processing logic
# ==========================================
async def process_github_pr(repo_full_name: str, pr_number: int):
    """[GitHub] Get PR differences and post a comment of review results"""
    try:
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3.diff",  # get diff
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
            # Get PR Diff
            diff_url = f"{GITHUB_URL}/repos/{repo_full_name}/pulls/{pr_number}"
            diff_resp = await client.get(diff_url, headers=headers)
            diff_text = diff_resp.text

            if not diff_text.strip():
                return

            # Execute LLM review
            review_result = await get_ollama_review(diff_text)

            # Post a comment to PR with JSON
            comment_headers = {
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
            }
            comment_url = f"{GITHUB_URL}/repos/{repo_full_name}/issues/{pr_number}/comments"
            comment_body = f"🤖 **AI Code Reviewer (GitHub)**\n\n{review_result}"
            await client.post(comment_url, headers=comment_headers, json={"body": comment_body})

    except Exception as e:
        print(f"GitHub Review Error: {e}")


# ==========================================
# GitLab processing logic
# ==========================================
async def process_gitlab_mr(project_id: int, mr_iid: int):
    """[GitLab] Get MR differences and post a comment of review results"""
    try:
        headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
        async with httpx.AsyncClient(timeout=300.0) as client:
            # Get changes in MR
            diff_url = f"{GITLAB_URL}/api/v4/projects/{project_id}/merge_requests/{mr_iid}/changes"
            diff_resp = await client.get(diff_url, headers=headers)
            changes = diff_resp.json().get("changes", [])

            diff_text = ""
            for change in changes:
                diff_text += f"\n--- File: {change['new_path']} ---\n"
                diff_text += change.get("diff", "")

            if not diff_text.strip():
                return

            # Execute review
            review_result = await get_ollama_review(diff_text)

            # Post a comment to MR
            note_url = f"{GITLAB_URL}/api/v4/projects/{project_id}/merge_requests/{mr_iid}/notes"
            comment_body = f"🤖 **AI Code Reviewer (GitLab)**\n\n{review_result}"
            await client.post(note_url, headers=headers, json={"body": comment_body})

    except Exception as e:
        print(f"GitLab Review Error: {e}")


# ==========================================
# Webhook endpoint
# ==========================================
@app.post("/webhook")
async def webhook_handler(
    request: Request, 
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None)
):
    # get a request body to verify
    body = await request.body()
    # verify signature. Return 401 if failure
    verify_github_signature(body, x_hub_signature_256)
    payload = await request.json()

    # --- Event determination for GitHub ---
    if PLATFORM == "github" or "pull_request" in payload:
        if "comment" in payload:
            comment_body = payload["comment"]["body"].strip()
            
            # If a commnet begins with "/review"
            if comment_body.startswith("/review") and "pull_request" in payload["issue"]:
                repo_full_name = payload["repository"]["full_name"]
                pr_number = payload["issue"]["number"]
                
                # Run review in background
                background_tasks.add_task(process_github_pr, repo_full_name, pr_number)
                return {"status": "accepted", "trigger": "github_comment_command"}
        elif "pull_request" in payload:
            # if PR opened or synchronize
            action = payload.get("action")
            if action in ["opened", "synchronize", "reopened"]:
                repo_full_name = payload["repository"]["full_name"]  # ex: "owner/repo"
                pr_number = payload["number"]
                background_tasks.add_task(process_github_pr, repo_full_name, pr_number)
                return {"status": "accepted", "platform": "github"}

    # --- Event determination for GitLab ---
    elif PLATFORM == "gitlab" or payload.get("object_kind") == "merge_request":
        object_kind = payload.get("object_kind")
        if object_kind == "note":
            comment_body = payload.get("object_attributes", {}).get("note", "").strip()
            noteable_type = payload.get("object_attributes", {}).get("noteable_type")
            
            # If a commnet begins with "/review"
            if comment_body.startswith("/review") and noteable_type == "MergeRequest":
                project_id = payload["project"]["id"]
                mr_iid = payload["merge_request"]["iid"]
                background_tasks.add_task(process_gitlab_mr, project_id, mr_iid)
                return {"status": "accepted", "trigger": "gitlab_comment_command"}
        elif object_kind == "merge_request":
            action = payload.get("object_attributes", {}).get("action")
            if action in ["open", "reopen", "update"]:
                project_id = payload["project"]["id"]
                mr_iid = payload["object_attributes"]["iid"]
                background_tasks.add_task(process_gitlab_mr, project_id, mr_iid)
                return {"status": "accepted", "platform": "gitlab"}

    return {"status": "ignored"}