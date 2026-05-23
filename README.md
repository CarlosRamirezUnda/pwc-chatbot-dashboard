# Personal Chatbot Dashboard

A full-stack **portfolio + AI assistant**: the left column renders structured resume data; the right column is a chatbot grounded only in that same resume. Powered by an **enterprise GenAI Proxy** (OpenAI-compatible API).

## Stack

| Layer    | Tech |
| -------- | ---- |
| Frontend | React 19, Vite, plain CSS, `fetch()` |
| Backend  | FastAPI, Uvicorn, pypdf, OpenAI Python SDK, python-dotenv |
| AI       | GenAI Proxy → `vertex_ai.gemini-2.5-flash` (configurable) |

## How it works

```
resume.pdf / resume.txt  →  backend loads on startup (in-memory)
                         →  GET /resume-data (LLM JSON extraction + regex fallback, cached)
                         →  POST /chat (Q&A with resume context + conversation history)
                         →  React frontend fetches and renders portfolio + chat
```

1. Place your resume at `backend/data/resume.pdf` (or set `RESUME_FILE`).
2. On startup, the backend extracts text with **pypdf** and builds a cached portfolio JSON object.
3. The frontend loads `/resume-data` for the hero, experience, education, languages, skills, and projects.
4. Each chat message goes to **`/v1/chat/completions`** via the GenAI Proxy with the full resume in the system prompt.
5. The assistant must not invent facts; missing info is answered with: *"The resume does not contain that information."*

> **Note:** Resume text and portfolio cache live in server memory. Restart the backend after changing `data/resume.pdf`.

## Features

### Portfolio (left)
- Hero with profile image, name, title, summary, contact
- Experience, formation/education, languages, skills
- Projects section only when the resume lists projects
- **Ask the assistant** — sends the same prompt as “Summarize this candidate”

### Chatbot (right)
- Conversation history (last 15 turns sent to the model)
- Suggested questions
- Response modes: `professional`, `recruiter_summary`, `interview_prep`, `short_answer`

## Prerequisites

- [Node.js](https://nodejs.org/) 18+
- [Python](https://www.python.org/) 3.10+
- Access to the **GenAI Proxy** (API key and internal base URL)

## 1. Backend setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `backend/.env`:

```env
GENAI_API_KEY=your_token_here
GENAI_BASE_URL=https://genai-sharedservice-americas.pwcinternal.com
GENAI_MODEL=vertex_ai.gemini-2.5-flash
RESUME_FILE=data/resume.pdf
CORS_ORIGINS=http://localhost:5173
```

Add your resume:

```text
backend/data/resume.pdf
```

Start the API:

```powershell
uvicorn main:app --reload --port 8000
```

On startup you should see logs like:

```text
INFO: GenAI model: vertex_ai.gemini-2.5-flash
INFO: GenAI base URL: https://genai-sharedservice-americas.pwcinternal.com
INFO: GenAI API key configured: True
```

API docs: http://localhost:8000/docs

## 2. Frontend setup

Open a **second terminal**:

```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```

Open http://localhost:5173

Optional `frontend/.env`:

```env
VITE_API_URL=http://localhost:8000
```

## 3. Use the app

1. Ensure `backend/data/resume.pdf` exists and the API is running.
2. Refresh the dashboard — portfolio sections load from `/resume-data`.
3. Ask questions in the chat or use suggested prompts / **Ask the assistant**.
4. Change response mode (professional, recruiter summary, interview prep, short answer) as needed.

Example questions:

- Summarize this candidate
- What are the candidate's strongest skills?
- What experience is listed for software development roles?

## API endpoints

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/health` | Health check |
| GET | `/resume/status` | `{ loaded, filename, source, word_count }` |
| GET | `/resume-data` | Structured portfolio JSON (cached) |
| POST | `/chat` | `{ message, history, response_mode }` → `{ reply }` |
| POST | `/upload` | Optional PDF upload (legacy; UI uses file on disk) |

### `POST /chat` body

```json
{
  "message": "Summarize this candidate",
  "history": [{ "role": "user", "content": "..." }, { "role": "assistant", "content": "..." }],
  "response_mode": "professional"
}
```

`response_mode`: `professional` (default), `recruiter_summary`, `interview_prep`, `short_answer`.

## Environment variables

**Backend (`backend/.env`)**

| Variable | Description |
| -------- | ----------- |
| `GENAI_API_KEY` | Required — GenAI Proxy bearer token |
| `GENAI_BASE_URL` | Proxy host (OpenAI SDK appends `/v1/chat/completions`) |
| `GENAI_MODEL` | Default: `vertex_ai.gemini-2.5-flash` |
| `RESUME_FILE` | Path to resume, e.g. `data/resume.pdf` |
| `CORS_ORIGINS` | Default: `http://localhost:5173` |

**Frontend (`frontend/.env`)**

| Variable | Description |
| -------- | ----------- |
| `VITE_API_URL` | Default: `http://localhost:8000` |

## Project structure

```
personal-chatbot-dashboard/
├── frontend/
│   ├── src/
│   │   ├── App.jsx       # Portfolio + chat UI
│   │   ├── App.css
│   │   └── main.jsx
│   └── package.json
├── backend/
│   ├── main.py           # FastAPI app, /chat, /resume-data
│   ├── genai_client.py   # OpenAI SDK → GenAI Proxy
│   ├── resume_parser.py  # Portfolio extraction + regex fallback
│   ├── data/
│   │   └── resume.pdf    # Primary resume (gitignored)
│   ├── requirements.txt
│   └── .env.example
├── PROJECT_CONTEXT.md    # Architecture notes for contributors/agents
└── README.md
```

## Profile image (frontend)

The hero uses a preview URL in `frontend/src/App.jsx`:

```javascript
const PROFILE_IMAGE_SRC = '...';
```

To use your photo: put `profile.jpg` in `frontend/public/` and set `PROFILE_IMAGE_SRC = '/profile.jpg'`.

## Troubleshooting

- **`GENAI_API_KEY is not configured`** — Create `backend/.env` from `.env.example` and set `GENAI_API_KEY`.
- **Invalid GenAI API key (401)** — Verify token and proxy access on your network/VPN.
- **Could not reach the GenAI proxy (502)** — Check `GENAI_BASE_URL` and corporate network access.
- **Portfolio empty / assistant unavailable** — Add `backend/data/resume.pdf` and restart the API.
- **Could not extract text from PDF** — Use a text-based PDF, not a scanned image-only file.
- **CORS errors** — Backend on port 8000; `CORS_ORIGINS` must include the frontend URL.
- **Stale portfolio after resume edit** — Restart uvicorn to rebuild the cache.

## AI client notes

- The backend uses the **OpenAI Python SDK** against the enterprise **GenAI Proxy**, not `google-generativeai`.
- Chat and `/resume-data` extraction share `genai_client.py` (`chat.completions.create`).
- If LLM extraction fails, `resume_parser.py` falls back to regex parsing of the raw resume text.

## License

MIT — use and modify freely for your portfolio.
