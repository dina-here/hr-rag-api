# Render Deployment Guide

## Prerequisites
- GitHub account with this repo pushed
- Render account (sign up at https://render.com)
- Secrets ready: `GEMINI_API_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX_HOST`

## Step-by-Step

### 1. Push to GitHub
```bash
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/youruser/yourrepo.git
git push -u origin main
```

### 2. Create Render Service

#### Option A: Blueprint (Recommended)
1. Go to https://dashboard.render.com/
2. Click **New** → **Blueprint**
3. Connect your GitHub account
4. Select your repo
5. Render detects `render.yaml` and shows preview
6. Set **Secret Environment Variables** (not in YAML):
   - `GEMINI_API_KEY`
   - `PINECONE_API_KEY`
   - `PINECONE_INDEX_HOST`
7. Click **Apply**

#### Option B: Manual Web Service
1. Click **New** → **Web Service**
2. Connect GitHub repo
3. Configure:
   - **Name**: `hr-rag-api`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port 10000`
4. Add Environment Variables:
   ```
   GEMINI_API_KEY=your_key
   PINECONE_API_KEY=your_key
   PINECONE_INDEX_HOST=hr-xxxxx.svc.aped-4627-b74a.pinecone.io
   PINECONE_NAMESPACE=hr
   DOCS_DIR=documents
   GITHUB_DOC_BASE_URL=https://raw.githubusercontent.com/youruser/yourrepo/main/documents/
   SYSTEM_PROMPT_PATH=system_prompt.txt
   EMBED_DIM=768
   ```
5. Click **Create Web Service**

### 3. Wait for Deploy
- First deploy: 2-3 minutes
- Watch logs in real-time on Render dashboard
- Service URL: `https://your-app-name.onrender.com`

### 4. Test Live API
```bash
# Health check
curl https://your-app-name.onrender.com/

# Chat request
curl -X POST https://your-app-name.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the vacation policy?", "history": []}'
```

### 5. Auto-Deploy on Push
Render automatically redeploys on every `git push` to main branch. To disable:
1. Go to service settings
2. **Auto-Deploy** → Off

## Updating Documents
Run ingestion locally (points to same Pinecone index):
```bash
python ingest_hr_docs.py
```
No need to redeploy Render - it queries the same index.

## Troubleshooting

### Build Fails
- Check Python version in `render.yaml` matches repo
- Verify `requirements.txt` has all deps
- Check Render logs for specific error

### Service Starts but 500 Errors
- Verify all environment variables are set
- Check `PINECONE_INDEX_HOST` format (no `https://`)
- Ensure Pinecone index dimension = `EMBED_DIM`

### Gemini Quota Errors
- Check API key is valid
- Monitor usage at https://ai.dev/usage
- Upgrade plan if needed

### Slow First Request
- Render free tier spins down after 15min inactivity
- First request "wakes" the service (~30s)
- Keep-alive services available on paid plans

## Monitoring
- Render dashboard shows metrics, logs, events
- Add external monitoring (UptimeRobot, etc.)
- Set up email alerts in Render settings

## Custom Domain
1. Go to service settings → **Custom Domains**
2. Add your domain
3. Configure DNS (CNAME or A record)
4. SSL auto-configured by Render
