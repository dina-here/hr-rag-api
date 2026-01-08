# HR RAG Demo

Small FastAPI + Gemini + Pinecone app. Ingest documents into Pinecone, then serve a chat endpoint that retrieves relevant chunks.

## Demo
- **Live API**: Deploy to Render and get a public URL
- **Local dev**: Run locally with hot-reload

## Prerequisites
- Python 3.12+ (venv recommended)
- Pinecone index (dim 768, dense)
- Gemini API access
- GitHub account (for Render deployment)
- Render account (free tier works)

## Setup (Local Development)

### 1) Clone and create virtual environment
```bash
# Clone your repo
git clone https://github.com/youruser/yourrepo.git
cd yourrepo

# Create and activate venv
python -m venv .venv

# Windows
.\.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2) Configure environment
- Copy `.env.example` to `.env`:
  ```bash
  cp .env.example .env
  ```
- Edit `.env` and fill in your actual values:
  - `GEMINI_API_KEY` → Get from [Google AI Studio](https://aistudio.google.com/apikey)
  - `OPENAI_API_KEY` → Get from [OpenAI Platform](https://platform.openai.com/api-keys) (optional, used as fallback if Gemini quota exceeded)
  - `PINECONE_API_KEY` → Get from [Pinecone Console](https://app.pinecone.io/)
  - `PINECONE_INDEX_HOST` → Your index endpoint (e.g., `hr-9dhfbmk.svc.aped-4627-b74a.pinecone.io`)
  - `PINECONE_NAMESPACE` → Default `hr` (can customize)
  - `DOCS_DIR` → Default `documents` (folder with PDFs/text files)
  - `GITHUB_DOC_BASE_URL` → Optional; set to your GitHub raw URL for source links (e.g., `https://raw.githubusercontent.com/youruser/yourrepo/main/documents/`)
  - `SYSTEM_PROMPT_PATH` → Default `system_prompt.txt`
  - `EMBED_DIM` → Default `768` (must match your Pinecone index dimension)

## Ingest documents (One-time Setup)
Place PDFs or text files in `documents/` (or your configured `DOCS_DIR`). Then run:

```bash
# With venv activated
python ingest_hr_docs.py

# Or specify Python directly
.\.venv\Scripts\python.exe ingest_hr_docs.py  # Windows
.venv/bin/python ingest_hr_docs.py           # macOS/Linux

# Dry-run to preview (no upload)
python ingest_hr_docs.py --dry-run
```

This uploads chunks to your Pinecone index/namespace. You only need to run this once, or when you update documents.

## Run API locally
```bash
# With venv activated
uvicorn app:app --reload --port 8000

# Or full path
.\.venv\Scripts\python.exe -m uvicorn app:app --reload --port 8000  # Windows
.venv/bin/python -m uvicorn app:app --reload --port 8000            # macOS/Linux
```

The API will be available at `http://localhost:8000`

### Test the API
Health check:
```bash
curl http://localhost:8000/
```

Chat endpoint (PowerShell):
```powershell
$body = @{ message = 'What is the vacation policy?' ; history = @() } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/chat -Body $body -ContentType 'application/json'
```

Chat endpoint (curl):
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the vacation policy?", "history": []}'
```

Request body format:
```json
{
  "message": "What is the vacation policy?",
  "history": [
    {"role": "user", "content": "Previous question"},
    {"role": "model", "content": "Previous answer"}
  ]
}
```

## Deploy on Render (via GitHub)

### Quick Deploy (Automated)
1. Push this repo to GitHub (ensure `.env` is NOT pushed - use `.gitignore`)
2. Go to [Render Dashboard](https://dashboard.render.com/)
3. Click **New** → **Blueprint** → Connect your GitHub repo
4. Render will detect `render.yaml` and auto-configure the service
5. Set the following **secret** environment variables in Render dashboard:
   - `GEMINI_API_KEY` → your Gemini API key
   - `PINECONE_API_KEY` → your Pinecone API key
   - `PINECONE_INDEX_HOST` → your Pinecone index endpoint (e.g., `hr-9dhfbmk.svc.aped-4627-b74a.pinecone.io`)
6. Optional: Update `GITHUB_DOC_BASE_URL` in `render.yaml` to your repo's raw URL
7. Click **Apply** to deploy

### Manual Deploy
If you prefer manual setup:
1. Push repo to GitHub
2. Create **New Web Service** in Render
3. Connect your GitHub repo
4. Configure:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port 10000`
5. Add all environment variables from `.env.example` in **Environment** tab
6. Deploy

### After Deployment
- Health check endpoint: `https://your-app.onrender.com/` → `{"status": "ok"}`
- Chat endpoint: `POST https://your-app.onrender.com/chat`
- First deploy may take 2-3 minutes; subsequent deploys are faster
- Render auto-redeploys on every `git push` to main branch

### Ingestion on Render
Since ingestion is a one-time setup, run it locally:
```bash
python ingest_hr_docs.py
```
This uploads chunks to Pinecone, which Render will then query. No need to re-run unless you update documents.

## Notes
- **Embeddings**: Uses `gemini-embedding-001` with `text-embedding-3-small` (OpenAI) as fallback. Vectors are automatically resized to match `EMBED_DIM` (default 768).
- **AI Fallback**: If Gemini quota is exceeded, the system automatically switches to OpenAI (if `OPENAI_API_KEY` is configured). Works for both chat generation and embeddings.
- **Citations**: When `GITHUB_DOC_BASE_URL` is set, source footers link to your hosted docs on GitHub. Leave empty for local file names only.
- **CORS**: Wide open for demo. For production, update `allow_origins` in [app.py](app.py#L28-L32).
- **Gemini Quotas**: If you hit rate limits, the API returns a fallback message with sources. Normal responses resume when quota refreshes.
- **Security**: Never commit `.env` (see `.gitignore`). Use Render dashboard for secrets in production.

## Project Structure
```
HR/
├── app.py                 # FastAPI server with /chat endpoint
├── rag_backend.py         # Pinecone query & embedding logic
├── ingest_hr_docs.py      # Document ingestion script
├── system_prompt.txt      # System instructions for Gemini
├── requirements.txt       # Python dependencies
├── render.yaml            # Render deployment config
├── .env.example           # Template for environment variables
├── .gitignore             # Excludes secrets and temp files
├── README.md              # This file
└── documents/             # Place your PDF/text files here
```

## Troubleshooting
- **Import errors**: Run `pip install -r requirements.txt` again
- **Pinecone 400 dimension mismatch**: Check `EMBED_DIM` matches your index dimension
- **Gemini 429 quota**: Wait for quota refresh or upgrade plan
- **No documents found**: Verify `DOCS_DIR` path and file permissions
- **Render deploy fails**: Check environment variables are set in dashboard, not `render.yaml` secrets

## Next Steps
- [ ] Customize `system_prompt.txt` for your organization
- [ ] Add authentication/API keys for production
- [ ] Implement chat history persistence
- [ ] Add frontend (React, Vue, etc.)
- [ ] Set up monitoring and logging
- [ ] Configure custom domain on Render
