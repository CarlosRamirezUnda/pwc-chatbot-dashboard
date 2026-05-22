# Personal Chatbot Dashboard

A full-stack resume chatbot: upload your PDF, ask questions, and get answers grounded only in your resume (powered by **Gemini Flash**).

## Stack

| Layer    | Tech                                      |
| -------- | ----------------------------------------- |
| Frontend | React, Vite, plain CSS, `fetch()`         |
| Backend  | FastAPI, pypdf, google-generativeai       |
| AI       | Google Gemini Flash (free tier in AI Studio) |

## How it works

1. You upload a PDF from the dashboard.
2. The backend extracts text with **pypdf** and stores it in memory.
3. Each chat message is sent to **Gemini Flash** with the resume as context.
4. The assistant only answers from the resume; otherwise it says: *"The resume does not contain that information."*

> **Note:** Resume text is kept in server memory. It is cleared when you restart the backend.

## Prerequisites

- [Node.js](https://nodejs.org/) 18+
- [Python](https://www.python.org/) 3.10+
- A free [Google AI Studio](https://aistudio.google.com/) API key

## 1. Backend setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `backend/.env` and set your key:

```
GEMINI_API_KEY=your_key_here
```

Start the API:

```powershell
uvicorn main:app --reload --port 8000
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

## 3. Use the app

1. Click **Choose PDF** and select your resume.
2. Wait for “Resume uploaded successfully.”
3. Ask questions, for example:
   - What are my strongest technical skills?
   - Summarize my most recent role.
   - What education do I have?

## API endpoints

| Method | Path            | Description                    |
| ------ | --------------- | ------------------------------ |
| GET    | `/health`       | Health check                   |
| GET    | `/resume/status` | Whether a resume is loaded    |
| POST   | `/upload`       | Upload PDF (`file` form field) |
| POST   | `/chat`         | Send `{ "message", "history" }` |

## Environment variables

**Backend (`backend/.env`)**

| Variable         | Description                          |
| ---------------- | ------------------------------------ |
| `GEMINI_API_KEY` | Required — from Google AI Studio     |
| `GEMINI_MODEL`   | Default: `gemini-2.0-flash`          |
| `CORS_ORIGINS`   | Default: `http://localhost:5173`     |

**Frontend (`frontend/.env`)**

| Variable       | Description                    |
| -------------- | ------------------------------ |
| `VITE_API_URL` | Default: `http://localhost:8000` |

## Troubleshooting

- **“GEMINI_API_KEY is not configured”** — Create `backend/.env` from `.env.example`.
- **“Could not extract text from PDF”** — Use a text-based PDF, not a scanned image-only file.
- **CORS errors** — Ensure the backend is on port 8000 and `CORS_ORIGINS` includes your frontend URL.
- **Chat blocked** — Upload a PDF before sending messages.

## Project structure

```
personal-chatbot-dashboard/
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── main.jsx
│   └── package.json
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── uploads/
│   └── .env.example
└── README.md
```

## Free-tier notes

- **Gemini Flash** — Free quota in [Google AI Studio](https://aistudio.google.com/); watch rate limits.
- **Local dev** — No hosting cost while building.
- For deployment later, consider Render (API) + Vercel (frontend); both have free tiers.

## License

MIT — use and modify freely for your portfolio.
