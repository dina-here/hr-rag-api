# app.py
import os
from pathlib import Path
from typing import List
import logging
import requests

from dotenv import load_dotenv
from datetime import datetime, timezone
from threading import Lock
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from google import genai
from google.genai import errors as genai_errors
from openai import OpenAI

from rag_backend import get_hr_policy, build_sources_markdown

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SYSTEM_PROMPT_PATH = os.getenv("SYSTEM_PROMPT_PATH", "system_prompt.txt")
# SYSTEM_PROMPT_PATH = os.getenv("SYSTEM_PROMPT_PATH", "../system_prompt.txt")

MODEL_ID = "gemini-2.0-flash"  # any chat-capable Gemini model you have access to 
OPENAI_MODEL = "gpt-5.2-chat-latest"  # OpenAI fallback model
SYSTEM_PROMPT = Path(SYSTEM_PROMPT_PATH).read_text(encoding="utf-8")

client = genai.Client(api_key=GEMINI_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

app = FastAPI(title="HR Policy Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Simple in-memory metrics
_metrics_lock = Lock()
METRICS = {
    "start_time": datetime.now(timezone.utc).isoformat(),
    "requests": 0,
    "errors": 0,
    "gemini_calls": 0,
    "openai_calls": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
}


class Message(BaseModel):
    role: str  # "user" or "model"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[Message] = []
    
    @property
    def validated_message(self):
        """Enforce max 200 characters per message for token control"""
        return self.message[:200] if len(self.message) > 200 else self.message


class ChatResponse(BaseModel):
    reply: str


@app.get("/")
def root():
    """Serve the chat interface"""
    return FileResponse("static/index.html")


@app.get("/health")
def health():
    """Health check endpoint for monitoring"""
    return {"status": "ok", "service": "HR RAG API"}


@app.get("/metrics")
def metrics():
    """Return simple runtime metrics for usage tracking"""
    with _metrics_lock:
        return METRICS.copy()


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    # Input validation: limit to 200 chars to control tokens
    message = req.validated_message
    with _metrics_lock:
        METRICS["requests"] += 1
    
    # 1) Call the "get_hr_policy tool" – same as n8n agent would do
    docs = get_hr_policy(message, top_k=3)
    sources_md = build_sources_markdown(docs)

    # Concatenate retrieved snippets - limit to 2000 chars for token control
    context = "\n\n".join(f"- {d['text']}" for d in docs)[:2000]

    # 2) Build instruction that includes:
    #    - the original system prompt from system_prompt.txt
    #    - the current retrieved snippets (“source data”)
    system_and_context = (
        SYSTEM_PROMPT
        + "\n\n### Source data from get_hr_policy:\n"
        + context
    )

    # 3) Convert into Gemini-style contents
    contents = [{"role": "user", "parts": [{"text": system_and_context}]}]
    for m in req.history:
        contents.append({"role": m.role, "parts": [{"text": m.content}]})
    contents.append({"role": "user", "parts": [{"text": message}]})

    answer = None
    
    # Try Gemini first
    try:
        result = client.models.generate_content(
            model=MODEL_ID,
            contents=contents,
        )
        answer = result.text.strip()
        # Collect Gemini usage if available
        try:
            usage = getattr(result, "usage_metadata", None)
            prompt_t = getattr(usage, "prompt_token_count", 0) if usage else 0
            completion_t = getattr(usage, "candidates_token_count", 0) if usage else 0
            total_t = getattr(usage, "total_token_count", 0) if usage else (prompt_t + completion_t)
            with _metrics_lock:
                METRICS["gemini_calls"] += 1
                METRICS["prompt_tokens"] += int(prompt_t or 0)
                METRICS["completion_tokens"] += int(completion_t or 0)
                METRICS["total_tokens"] += int(total_t or 0)
            logger.info(f"Gemini tokens: prompt={prompt_t}, completion={completion_t}, total={total_t}")
        except Exception as _:
            # Non-fatal if usage not available
            pass
    except genai_errors.ClientError as e:
        # Log Gemini error
        logger.error(f"Gemini error: {e}")
        # Fallback to OpenAI on Gemini errors when available
        if openai_client:
            try:
                # Convert history to OpenAI format
                openai_messages = [
                    {"role": "system", "content": system_and_context}
                ]
                for m in req.history:
                    openai_messages.append({
                        "role": "assistant" if m.role == "model" else m.role,
                        "content": m.content
                    })
                openai_messages.append({"role": "user", "content": message})
                
                # Call OpenAI with gpt-5.2-chat-latest
                response = openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=openai_messages,
                    max_completion_tokens=400,
                )
                answer = response.choices[0].message.content.strip()
                # Collect OpenAI usage
                try:
                    usage = getattr(response, "usage", None)
                    prompt_t = getattr(usage, "prompt_tokens", None)
                    completion_t = getattr(usage, "completion_tokens", None)
                    total_t = getattr(usage, "total_tokens", None)
                    with _metrics_lock:
                        METRICS["openai_calls"] += 1
                        METRICS["prompt_tokens"] += int(prompt_t or 0)
                        METRICS["completion_tokens"] += int(completion_t or 0)
                        METRICS["total_tokens"] += int(total_t or 0)
                    logger.info(f"OpenAI tokens: prompt={prompt_t}, completion={completion_t}, total={total_t}")
                except Exception:
                    with _metrics_lock:
                        METRICS["openai_calls"] += 1
            except Exception as oe:
                # Log OpenAI error
                logger.error(f"OpenAI error: {oe}")
                with _metrics_lock:
                    METRICS["errors"] += 1
                answer = "I'm sorry, I can't answer that. Please contact HR"
        else:
            # No OpenAI configured
            logger.warning("OpenAI client not configured, using fallback")
            with _metrics_lock:
                METRICS["errors"] += 1
            answer = "I'm sorry, I can't answer that. Please contact HR"

    # 4) Append our own “Sources” footer (the prompt also asks for this style)
    answer_with_sources = answer + "\n\n" + sources_md

    return ChatResponse(reply=answer_with_sources)
