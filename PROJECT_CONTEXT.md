# Project Context — Personal Chatbot Dashboard

Personal portfolio site with a side chatbot. The left column shows resume-driven portfolio content; the right column is an AI assistant grounded in the same resume.

## Architecture

```
resume.pdf / resume.txt  →  backend loads on startup (in-memory)
                         →  /resume-data (Gemini JSON extraction, cached)
                         →  /chat (Gemini Q&A with resume context)
                         →  React frontend fetches and renders
```

- **Single resume file** is the source of truth for both portfolio UI and chatbot.
- **No database, auth, vector DB, or LangChain** — MVP in-memory only.
- Resume reload requires **backend restart** (or `POST /upload`, which is not used by the current UI).

## Tech Stack

| Layer | Stack |
|-------|-------|
| Frontend | React 19, Vite, plain CSS, `fetch()` |
| Backend | FastAPI, Uvicorn, pypdf, google-generativeai, python-dotenv |
| AI | Gemini Flash (`gemini-2.5-flash` default) |

## Project Structure

```
personal-chatbot-dashboard/
├── frontend/src/
│   ├── App.jsx      # Portfolio + chat UI (single component)
│   ├── App.css      # Dark premium styling
│   └── main.jsx
├── backend/
│   ├── main.py           # FastAPI app, /chat, /resume-data
│   ├── resume_parser.py  # Gemini portfolio extraction + regex fallback
│   ├── data/resume.pdf   # Primary resume location (gitignored)
│   ├── requirements.txt
│   └── .env              # GEMINI_API_KEY, RESUME_FILE, CORS_ORIGINS
└── README.md
```

## Backend Responsibilities

- Load resume from file on startup (priority: `RESUME_FILE` env → `data/resume.pdf` → `data/resume.txt` → root fallbacks).
- Extract PDF text with **pypdf**; read `.txt` directly.
- Store `_resume_text` in memory for chat.
- Build and cache structured portfolio JSON via `build_resume_data()` on startup.
- Expose REST endpoints with CORS for `http://localhost:5173`.

## Frontend Responsibilities

- Fetch `GET /resume-data` on load → store in `resumeData` state (normalized via `normalizeResumeData()`).
- Render portfolio: hero, skills, experience, education, projects (conditional).
- Fetch `GET /resume/status` for chat availability indicator.
- Send `POST /chat` with message, history, and `response_mode`.
- **No Tailwind, no extra UI libraries.**

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| GET | `/resume/status` | `{ loaded, filename, source, word_count }` |
| GET | `/resume-data` | Structured portfolio JSON (cached) |
| POST | `/chat` | AI reply grounded in resume |
| POST | `/upload` | Optional PDF upload (legacy; UI does not use it) |

### `POST /chat` request

```json
{
  "message": "string",
  "history": [{ "role": "user|assistant", "content": "string" }],
  "response_mode": "professional"
}
```

`response_mode` values: `professional` (default), `recruiter_summary`, `interview_prep`, `short_answer`.

### `POST /chat` response

```json
{ "reply": "string" }
```

### `GET /resume-data` response shape

```json
{
  "name": "Juan Carlos Ramírez Unda",
  "title": "Computer Science Student",
  "summary": "Committed to process innovation and optimization...",
  "email": "carlosunda01@gmail.com",
  "phone": "5584105206",
  "links": [
    { "label": "LinkedIn", "url": "https://linkedin.com/in/..." }
  ],
  "skills": ["Python", "JavaScript", "SQL", "React Native", "SCRUM"],
  "projects": [],
  "experience": [
    {
      "title": "Applications Tester and Documentation Assistant",
      "company": "América Movil Group",
      "period": "2025",
      "highlights": ["Developed and standardized manuals..."]
    }
  ],
  "education": [
    {
      "degree": "Technical Degree in Programming",
      "school": "Colegios de Estudios Científicos y Tecnológicos de Estado de Mexico",
      "year": "2021"
    }
  ],
  "source": "data/resume.pdf"
}
```

Empty sections return `[]` or `""`. Frontend hides sections with no items.

## Features

### Portfolio (left column)
- Hero: name, title, summary, email, phone, links, “Ask the assistant” CTA.
- **Skills** — pill/chip list (shown if items exist).
- **Experience** — title, company, period, highlight bullets.
- **Education** — degree, school, year.
- **Projects** — only if non-empty.

### Chatbot (right column)
- Message history with loading state.
- **Suggested Questions** — clickable presets that call the same `handleSend()` flow.
- **Recruiter Mode** — dropdown sends `response_mode` with each chat request.

## UI Decisions

- **Dark premium theme** — surface cards, blue accent, sticky chat sidebar on desktop.
- **Layout** — two columns (portfolio | chat) on desktop; stacked on mobile.
- **Typography** — readable sizes; title in sentence case (not giant all-caps).
- **Conditional sections** — hide empty projects/education; no placeholder cards.
- Chat panel styling is separate from portfolio but visually consistent.

## Gemini Behavior

### Chat (`/chat`)
- System prompt embeds full resume text.
- Must not invent facts; say *"The resume does not contain that information."* when missing.
- `response_mode` appends a style instruction (professional, recruiter, interview prep, short).
- History capped at 15 turns. Temperature 0.3.
- 429 quota errors return a friendly message.

### Portfolio extraction (`/resume-data`)
- Separate prompt in `resume_parser.py` requests **JSON only** (`response_mime_type: application/json`).
- Resume is source of truth; skills may be inferred only if resume-supported.
- **Regex parser fallback** if Gemini fails.
- Result cached in `_resume_portfolio_cache` at startup.

## Environment Variables

**Backend (`backend/.env`)**
- `GEMINI_API_KEY` — required
- `GEMINI_MODEL` — default `gemini-2.5-flash`
- `CORS_ORIGINS` — default `http://localhost:5173`
- `RESUME_FILE` — e.g. `data/resume.pdf`

**Frontend (`frontend/.env`)**
- `VITE_API_URL` — default `http://localhost:8000`

## Important Constraints (for future changes)

1. **Resume is source of truth** — never invent employers, dates, skills, projects, or achievements.
2. **Keep `/chat` stable** — do not break Gemini integration, history, or `response_mode` without good reason.
3. **Minimal diffs** — avoid overengineering (no auth, DB, embeddings, or deployment complexity unless explicitly requested).
4. **Frontend uses plain CSS** — no Tailwind.
5. **Portfolio and chat share the same resume file** — update `backend/data/resume.pdf` and restart backend.
6. **Do not commit** `.env`, `data/resume.pdf`, or secrets.

## Local Run

```powershell
# Backend
cd backend
.\.venv\Scripts\python -m uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm run dev
```

Open http://localhost:5173 — API docs at http://localhost:8000/docs.
