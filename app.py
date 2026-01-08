# app.py
import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import errors as genai_errors

from rag_backend import get_hr_policy, build_sources_markdown

load_dotenv()

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
SYSTEM_PROMPT_PATH = os.getenv("SYSTEM_PROMPT_PATH", "system_prompt.txt")
# SYSTEM_PROMPT_PATH = os.getenv("SYSTEM_PROMPT_PATH", "../system_prompt.txt")

MODEL_ID = "gemini-2.0-flash"  # any chat-capable Gemini model you have access to 
SYSTEM_PROMPT = Path(SYSTEM_PROMPT_PATH).read_text(encoding="utf-8")

client = genai.Client(api_key=GEMINI_API_KEY)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Message(BaseModel):
    role: str  # "user" or "model"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[Message] = []


class ChatResponse(BaseModel):
    reply: str


@app.get("/")
def health():
    return {"status": "ok", "service": "HR RAG API"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    # 1) Call the “get_hr_policy tool” – same as n8n agent would do
    docs = get_hr_policy(req.message, top_k=5)
    sources_md = build_sources_markdown(docs)

    # Concatenate retrieved snippets for Gemini
    context = "\n\n".join(f"- {d['text']}" for d in docs)[:4000]

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
    contents.append({"role": "user", "parts": [{"text": req.message}]})

    try:
        result = client.models.generate_content(
            model=MODEL_ID,
            contents=contents,
        )
        answer = result.text.strip()
    except genai_errors.ClientError:
        answer = "I’m sorry, I can’t answer that. Please contact HR"

    # 4) Append our own “Sources” footer (the prompt also asks for this style)
    answer_with_sources = answer + "\n\n" + sources_md

    return ChatResponse(reply=answer_with_sources)
