import { useEffect, useRef, useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const SUGGESTED_QUESTIONS = [
  'Summarize this candidate',
  "What are the candidate's strongest skills?",
  'What projects are listed in the resume?',
  'Is this candidate a good fit for a frontend role?',
];

const RESPONSE_MODES = [
  { value: 'professional', label: 'Professional' },
  { value: 'recruiter_summary', label: 'Recruiter Summary' },
  { value: 'interview_prep', label: 'Interview Prep' },
  { value: 'short_answer', label: 'Short Answer' },
];

let messageId = 0;
function nextId() {
  messageId += 1;
  return String(messageId);
}

async function parseError(res) {
  try {
    const data = await res.json();
    if (typeof data?.detail === 'string') return data.detail;
    if (Array.isArray(data?.detail)) {
      return data.detail.map((d) => d.msg || String(d)).join(', ');
    }
  } catch {
    /* ignore */
  }
  return 'Request failed. Check that the API is running.';
}

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const [resumeStatus, setResumeStatus] = useState({ loaded: false, filename: null, word_count: 0 });
  const [uploadStatus, setUploadStatus] = useState('idle'); // idle | uploading | success | error
  const [uploadMessage, setUploadMessage] = useState('');
  const [responseMode, setResponseMode] = useState('professional');

  const fileInputRef = useRef(null);
  const chatEndRef = useRef(null);

  async function refreshResumeStatus() {
    try {
      const res = await fetch(`${API_URL}/resume/status`);
      if (res.ok) {
        const data = await res.json();
        setResumeStatus(data);
      }
    } catch {
      setResumeStatus({ loaded: false, filename: null, word_count: 0 });
    }
  }

  useEffect(() => {
    refreshResumeStatus();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setUploadStatus('error');
      setUploadMessage('Please select a PDF file.');
      return;
    }

    setError('');
    setUploadStatus('uploading');
    setUploadMessage('Uploading and extracting text…');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_URL}/upload`, {
        method: 'POST',
        body: formData,
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(await parseError(res));
      }

      setUploadStatus('success');
      setUploadMessage(
        `Loaded "${data.filename}" (${data.word_count} words). You can ask questions now.`,
      );
      setMessages([]);
      await refreshResumeStatus();
    } catch (err) {
      setUploadStatus('error');
      setUploadMessage(err.message || 'Upload failed.');
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  async function handleSend(text) {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;

    if (!resumeStatus.loaded) {
      setError('Upload your resume PDF before chatting.');
      return;
    }

    setError('');
    const userMessage = { id: nextId(), role: 'user', content: trimmed };
    const history = messages.map(({ role, content }) => ({ role, content }));

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: trimmed, history, response_mode: responseMode }),
      });

      if (!res.ok) {
        throw new Error(await parseError(res));
      }

      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: 'assistant', content: data.reply },
      ]);
    } catch (err) {
      setError(err.message || 'Something went wrong.');
    } finally {
      setIsLoading(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    handleSend(input);
  }

  return (
    <div className="app">
      <header className="header">
        <h1>Personal Chatbot Dashboard</h1>
        <p className="subtitle">
          Upload your resume PDF, then ask about experience, skills, projects, and education.
          Answers use only your uploaded resume.
        </p>
      </header>

      <section className="upload-panel">
        <h2>Resume upload</h2>
        <div className="upload-row">
          <label className="upload-label">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              onChange={handleUpload}
              disabled={uploadStatus === 'uploading'}
            />
            <span className="upload-button">Choose PDF</span>
          </label>
          {resumeStatus.loaded && (
            <span className="resume-badge">
              Active: {resumeStatus.filename} ({resumeStatus.word_count} words)
            </span>
          )}
        </div>
        {uploadStatus !== 'idle' && (
          <p className={`upload-status upload-status--${uploadStatus}`}>{uploadMessage}</p>
        )}
      </section>

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      <main className="chat-panel">
        <div className="messages" aria-live="polite">
          {messages.length === 0 && !isLoading && (
            <p className="empty-state">
              {resumeStatus.loaded
                ? 'Ask a question about your resume — for example: "What are my top skills?"'
                : 'Upload a PDF to start chatting.'}
            </p>
          )}
          {messages.map((msg) => (
            <div key={msg.id} className={`message message--${msg.role}`}>
              <span className="message-label">{msg.role === 'user' ? 'You' : 'Assistant'}</span>
              <p>{msg.content}</p>
            </div>
          ))}
          {isLoading && (
            <div className="message message--assistant message--loading">
              <span className="message-label">Assistant</span>
              <p className="typing">Thinking…</p>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="chat-controls">
          <div className="suggested-questions">
            <span className="suggested-questions__label">Suggested questions</span>
            <div className="suggested-questions__list">
              {SUGGESTED_QUESTIONS.map((question) => (
                <button
                  key={question}
                  type="button"
                  className="suggested-questions__btn"
                  onClick={() => handleSend(question)}
                  disabled={isLoading || !resumeStatus.loaded}
                >
                  {question}
                </button>
              ))}
            </div>
          </div>

          <label className="mode-select">
            <span className="mode-select__label">Response mode</span>
            <select
              value={responseMode}
              onChange={(e) => setResponseMode(e.target.value)}
              disabled={isLoading}
            >
              {RESPONSE_MODES.map((mode) => (
                <option key={mode.value} value={mode.value}>
                  {mode.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <form className="composer" onSubmit={handleSubmit}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              resumeStatus.loaded ? 'Ask about your resume…' : 'Upload a PDF first…'
            }
            disabled={isLoading || !resumeStatus.loaded}
          />
          <button type="submit" disabled={isLoading || !input.trim() || !resumeStatus.loaded}>
            Send
          </button>
        </form>
      </main>
    </div>
  );
}
