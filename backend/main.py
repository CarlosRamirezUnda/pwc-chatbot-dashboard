"""
Personal Chatbot Dashboard — FastAPI backend.
Upload a PDF resume, then chat grounded only in that text via Gemini Flash.
"""

from __future__ import annotations

import io
import os
from typing import Literal

import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pypdf import PdfReader

load_dotenv()

app = FastAPI(title="Personal Chatbot Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory resume store (MVP — resets when server restarts)
_resume_text: str | None = None
_resume_filename: str | None = None

SYSTEM_PROMPT = """
You are a professional career assistant representing the candidate.

Your source of truth is the RESUME text below.

You can:
- Answer questions about the candidate
- Summarize experience, skills, education, and projects
- Explain resume details in a professional way
- Infer reasonable professional strengths from the resume
- Adapt the answer for recruiters, interviews, or hiring managers

Rules:
- Do not invent employers, dates, degrees, certifications, skills, projects, metrics, or achievements.
- If a fact is not in the resume, say it is not listed in the resume.
- If the question asks for interpretation, give a helpful answer based on the resume.
- If the question asks for something completely missing, respond:
  "The resume does not contain that information."
- Be specific when the resume provides details.
- Use bullets when helpful.
- Keep a confident, polished, professional tone.
- Avoid repeating the same opening phrase in every response.
- Do not start every answer with "Based on your resume."
- Vary the wording naturally while still making it clear that the resume is the source of truth.
- If discussing gaps or areas for improvement, be constructive and specific.
- Do not exaggerate the candidates experience level.

RESUME:
{resume_text}
"""

MAX_HISTORY_TURNS = 15

ResponseMode = Literal[
    "professional",
    "recruiter_summary",
    "interview_prep",
    "short_answer",
]

MODE_STYLES: dict[str, str] = {
    "professional": (
        "Response style: Give a polished professional answer in 2–5 sentences. "
        "Be clear, confident, and specific. Highlight relevant resume evidence when possible."
    ),

    "recruiter_summary": (
        "Response style: Answer like a recruiter writing notes for a hiring manager. "
        "Focus on role fit, strongest qualifications, relevant skills, and any resume-based gaps. "
        "Use a balanced tone: positive but realistic. "
        "Do not overhype the candidate. Keep it concise and useful for hiring decisions."
    ),

    "interview_prep": (
        "Response style: Help the candidate prepare for interviews. "
        "Give practical talking points based on the resume. "
        "When useful, suggest how the candidate could explain their experience using simple interview language. "
        "Do not invent examples, metrics, or achievements not found in the resume."
    ),

    "short_answer": (
        "Response style: Answer in 1–2 concise sentences only. "
        "Be direct. Do not use bullet points unless the user explicitly asks."
    ),
}


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list)
    response_mode: ResponseMode = "professional"


class ChatResponse(BaseModel):
    reply: str


def extract_pdf_text(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid or corrupted PDF file.") from exc

    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)

    full_text = "\n".join(pages).strip()
    if not full_text:
        raise HTTPException(
            status_code=400,
            detail="Could not extract text from PDF. Try a text-based PDF (not a scanned image).",
        )
    return full_text


def get_gemini_reply(
    resume_text: str,
    message: str,
    history: list[ChatMessage],
    response_mode: ResponseMode = "professional",
) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")

    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    mode_style = MODE_STYLES.get(response_mode, MODE_STYLES["professional"])
    system_instruction = SYSTEM_PROMPT.format(resume_text=resume_text) + "\n\n" + mode_style

    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_instruction,
        generation_config={"temperature": 0.3, "max_output_tokens": 1024},
    )

    capped = history[-MAX_HISTORY_TURNS:] if len(history) > MAX_HISTORY_TURNS else history
    contents: list[dict] = []
    for item in capped:
        role = "user" if item.role == "user" else "model"
        contents.append({"role": role, "parts": [item.content]})
    contents.append({"role": "user", "parts": [message]})

    try:
        response = model.generate_content(contents)
    except Exception as exc:
        err = str(exc)
        if "429" in err or "quota" in err.lower() or "Quota exceeded" in err:
            raise HTTPException(
                status_code=429,
                detail=(
                    "Gemini API quota exceeded. Wait a minute and try again, "
                    "or set GEMINI_MODEL to another free model (e.g. gemini-2.5-flash) in backend/.env. "
                    "Check usage: https://ai.dev/rate-limit"
                ),
            ) from exc
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}") from exc

    reply = getattr(response, "text", None)
    if not reply:
        raise HTTPException(status_code=502, detail="AI service returned an empty response.")
    return reply.strip()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/resume/status")
def resume_status():
    return {
        "loaded": _resume_text is not None,
        "filename": _resume_filename,
        "word_count": len(_resume_text.split()) if _resume_text else 0,
    }


@app.post("/upload")
async def upload_resume(file: UploadFile = File(...)):
    global _resume_text, _resume_filename

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="PDF must be smaller than 10 MB.")

    text = extract_pdf_text(content)
    _resume_text = text
    _resume_filename = file.filename

    return {
        "message": "Resume uploaded successfully.",
        "filename": _resume_filename,
        "word_count": len(text.split()),
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if _resume_text is None:
        raise HTTPException(
            status_code=400,
            detail="No resume loaded. Upload a PDF first.",
        )

    reply = get_gemini_reply(
        _resume_text,
        request.message.strip(),
        request.history,
        request.response_mode,
    )
    return ChatResponse(reply=reply)
