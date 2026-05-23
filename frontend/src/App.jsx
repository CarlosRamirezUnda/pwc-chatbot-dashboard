import { useEffect, useRef, useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/** Preview profile photo — replace with your own (see README in response). */
const PROFILE_IMAGE_SRC =
  '/public/profile/profile.jpg';

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

const TITLE_SPLIT_WORDS = [
  'COMPUTER',
  'SCIENCE',
  'STUDENT',
  'SOFTWARE',
  'DEVELOPER',
  'ENGINEER',
  'PROGRAMMING',
  'ARTIFICIAL',
  'INTELLIGENCE',
  'DATA',
  'ANALYST',
  'INTERN',
  'FULL',
  'STACK',
  'WEB',
  'MOBILE',
  'TECHNICAL',
  'DEGREE',
];

function isSingleLetterSpaced(value) {
  const parts = String(value || '').trim().split(/\s+/).filter(Boolean);
  return parts.length >= 4 && parts.every((part) => part.length === 1 && /[A-Za-z]/.test(part));
}

function splitCompactUppercase(value) {
  const compact = String(value || '')
    .replace(/\s+/g, '')
    .toUpperCase();
  if (!compact || !/^[A-Z]+$/.test(compact) || compact.length < 8) {
    return String(value || '').trim();
  }

  const words = [];
  let index = 0;
  const sortedWords = [...TITLE_SPLIT_WORDS].sort((a, b) => b.length - a.length);

  while (index < compact.length) {
    let matched = false;
    for (const token of sortedWords) {
      if (compact.slice(index).startsWith(token)) {
        words.push(token.charAt(0) + token.slice(1).toLowerCase());
        index += token.length;
        matched = true;
        break;
      }
    }
    if (!matched) {
      let nextIndex = index + 1;
      while (nextIndex <= compact.length) {
        const hasNext = sortedWords.some((token) => compact.slice(nextIndex).startsWith(token));
        if (hasNext || nextIndex === compact.length) {
          const chunk = compact.slice(index, nextIndex);
          words.push(chunk.charAt(0) + chunk.slice(1).toLowerCase());
          index = nextIndex;
          matched = true;
          break;
        }
        nextIndex += 1;
      }
      if (!matched) break;
    }
  }

  return words.join(' ');
}

function formatProfessionalTitle(value) {
  const cleaned = String(value || '').trim();
  if (!cleaned) return '';

  if (isSingleLetterSpaced(cleaned)) {
    return splitCompactUppercase(cleaned.replace(/\s+/g, ''));
  }

  const compact = cleaned.replace(/\s+/g, '');
  if (compact === compact.toUpperCase() && /^[A-Z]+$/.test(compact) && compact.length >= 10) {
    return splitCompactUppercase(compact);
  }

  if (cleaned === cleaned.toUpperCase() && cleaned.length > 4) {
    return cleaned
      .toLowerCase()
      .replace(/\b[a-z]/g, (char) => char.toUpperCase());
  }

  return cleaned;
}

function isSpacedBanner(value) {
  const cleaned = String(value || '').trim();
  if (!cleaned) return false;
  if (isSingleLetterSpaced(cleaned)) return true;
  if (/\b[A-Z] [A-Z] /.test(cleaned)) return true;
  const lettersOnly = cleaned.replace(/\s+/g, '');
  return cleaned.length > 10 && cleaned === cleaned.toUpperCase() && lettersOnly.length < cleaned.length * 0.55;
}

function looksLikePersonName(value) {
  const parts = String(value || '').trim().split(/\s+/).filter(Boolean);
  return parts.length >= 2 && !isSpacedBanner(value) && value.trim() !== value.trim().toUpperCase();
}

function fixNameTitleSwap(name, title) {
  const resolvedName = String(name || '').trim();
  const resolvedTitle = String(title || '').trim();

  if (isSpacedBanner(resolvedName) && looksLikePersonName(resolvedTitle)) {
    return {
      name: resolvedTitle,
      title: formatProfessionalTitle(resolvedName),
    };
  }
  if (looksLikePersonName(resolvedName) && isSpacedBanner(resolvedTitle)) {
    return {
      name: resolvedName,
      title: formatProfessionalTitle(resolvedTitle),
    };
  }
  return { name: resolvedName, title: formatProfessionalTitle(resolvedTitle) };
}

function ensureStringArray(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean);
  }
  if (typeof value === 'string' && value.trim()) {
    if (value.includes(',') || value.includes(';')) {
      return value
        .split(/[,;]/)
        .map((part) => part.trim())
        .filter(Boolean);
    }
    return [value.trim()];
  }
  return [];
}

function normalizeLinks(raw) {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((link) => link && typeof link === 'object')
    .map((link) => ({
      label: String(link.label || '').trim(),
      url: String(link.url || '').trim(),
    }))
    .filter((link) => link.label && link.url);
}

function normalizeExperienceList(raw) {
  const items = Array.isArray(raw) ? raw : ensureStringArray(raw);
  if (!Array.isArray(items)) return [];

  return items
    .filter((item) => item && typeof item === 'object')
    .map((item) => {
      const title = String(item.title || item.role || item.position || '').trim();
      const company = String(item.company || item.employer || item.organization || '').trim();
      const period = String(item.period || item.dates || item.date || item.year || '').trim();
      const highlights = ensureStringArray(
        item.highlights ?? item.bullets ?? item.responsibilities ?? item.description,
      );
      return { title, company, period, highlights };
    })
    .filter((item) => item.title || item.company || item.highlights.length > 0);
}

function normalizeEducationList(raw) {
  const items = Array.isArray(raw) ? raw : ensureStringArray(raw);
  if (!Array.isArray(items)) return [];

  return items
    .filter((item) => item && typeof item === 'object')
    .map((item) => ({
      degree: String(item.degree || item.program || item.title || '').trim(),
      school: String(item.school || item.institution || item.university || '').trim(),
      year: String(item.year || item.period || item.date || '').trim(),
    }))
    .filter((item) => item.degree || item.school || item.year);
}

function normalizeProjectsList(raw) {
  const items = Array.isArray(raw) ? raw : ensureStringArray(raw);
  if (!Array.isArray(items)) return [];

  return items
    .filter((item) => item && typeof item === 'object')
    .map((item) => ({
      title: String(item.title || item.name || '').trim(),
      description: String(item.description || item.summary || '').trim(),
    }))
    .filter((item) => item.title || item.description);
}

function sortExperience(items) {
  if (!Array.isArray(items)) return [];
  return [...items].sort((a, b) => {
    const yearA = Number(String(a.period || '').match(/\d{4}/)?.[0] || 0);
    const yearB = Number(String(b.period || '').match(/\d{4}/)?.[0] || 0);
    return yearB - yearA;
  });
}

function normalizeResumeData(raw) {
  if (!raw || typeof raw !== 'object') return null;

  const { name, title } = fixNameTitleSwap(raw.name, raw.title);
  const educationSource = raw.education ?? raw.formation ?? [];

  return {
    name,
    title: formatProfessionalTitle(title),
    summary: String(raw.summary || raw.profile || raw.about || '').trim(),
    email: String(raw.email || '').trim(),
    phone: String(raw.phone || '').trim(),
    links: normalizeLinks(raw.links),
    skills: ensureStringArray(raw.skills),
    languages: ensureStringArray(raw.languages),
    projects: normalizeProjectsList(raw.projects),
    experience: sortExperience(normalizeExperienceList(raw.experience)),
    education: normalizeEducationList(educationSource),
    source: raw.source || null,
  };
}

function linkHref(url) {
  if (!url) return '#';
  return url.startsWith('http') || url.startsWith('mailto:') ? url : `https://${url}`;
}

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [resumeStatus, setResumeStatus] = useState({ loaded: false, filename: null, word_count: 0 });
  const [responseMode, setResponseMode] = useState('professional');
  const [resumeData, setResumeData] = useState(null);
  const [portfolioLoading, setPortfolioLoading] = useState(true);
  const [portfolioError, setPortfolioError] = useState('');

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

  async function fetchPortfolioData() {
    setPortfolioLoading(true);
    setPortfolioError('');
    try {
      const res = await fetch(`${API_URL}/resume-data`);
      if (!res.ok) {
        throw new Error(await parseError(res));
      }
      const data = await res.json();
      console.log('resume data:', data);
      setResumeData(normalizeResumeData(data));
    } catch (err) {
      setResumeData(null);
      setPortfolioError(err.message || 'Could not load portfolio data from resume.');
    } finally {
      setPortfolioLoading(false);
    }
  }

  useEffect(() => {
    refreshResumeStatus();
    fetchPortfolioData();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  async function handleSend(text) {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;

    if (!resumeStatus.loaded) {
      setError('Assistant unavailable. Add backend/data/resume.pdf and restart the API.');
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

  function handleAskAssistant() {
    document.getElementById('chat')?.scrollIntoView({ behavior: 'smooth' });
    handleSend(SUGGESTED_QUESTIONS[0]);
  }

  function renderPortfolioContent() {
    if (portfolioLoading) {
      return <p className="portfolio-state">Loading portfolio from resume…</p>;
    }

    if (portfolioError || !resumeData) {
      return (
        <p className="portfolio-state portfolio-state--error">
          {portfolioError || 'Portfolio data unavailable.'}
        </p>
      );
    }

    const skills = Array.isArray(resumeData.skills) ? resumeData.skills : [];
    const experience = Array.isArray(resumeData.experience) ? resumeData.experience : [];
    const education = Array.isArray(resumeData.education) ? resumeData.education : [];
    const languages = Array.isArray(resumeData.languages) ? resumeData.languages : [];
    const projects = Array.isArray(resumeData.projects) ? resumeData.projects : [];
    const links = Array.isArray(resumeData.links) ? resumeData.links : [];

    return (
      <div className="portfolio-sections">
        <section className="hero card hero--profile">
          <div className="hero__layout">
            <div className="hero__media">
              <div className="profile-image">
                <img
                  src={PROFILE_IMAGE_SRC}
                  alt={resumeData.name ? `${resumeData.name} profile` : 'Profile photo'}
                  className="profile-image__img"
                  width={200}
                  height={200}
                />
              </div>
            </div>
            <div className="hero__content">
              <p className="hero__eyebrow">Portfolio</p>
              {resumeData.name ? <h1 className="hero__name">{resumeData.name}</h1> : null}
              {resumeData.title ? <p className="hero__title">{resumeData.title}</p> : null}
              {resumeData.summary ? <p className="hero__intro">{resumeData.summary}</p> : null}
              <button
                type="button"
                className="hero__cta btn-primary"
                onClick={handleAskAssistant}
                disabled={isLoading || !resumeStatus.loaded}
              >
                Ask the assistant
              </button>
              {(resumeData.email || resumeData.phone || links.length > 0) && (
                <div className="hero__links">
                  {resumeData.email ? (
                    <a href={`mailto:${resumeData.email}`}>{resumeData.email}</a>
                  ) : null}
                  {resumeData.phone ? <span className="hero__phone">{resumeData.phone}</span> : null}
                  {links.map((link) => (
                    <a
                      key={`${link.label}-${link.url}`}
                      href={linkHref(link.url)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {link.label}
                    </a>
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>

        {experience.length > 0 && (
          <section className="card section-card">
            <h2 className="section-title">Experience</h2>
            <div className="item-list">
              {experience.map((job, index) => (
                <article key={`${job.title}-${job.company}-${index}`} className="item">
                  {job.title ? <h3 className="item__title">{job.title}</h3> : null}
                  {(job.company || job.period) && (
                    <p className="item__meta">
                      {[job.company, job.period].filter(Boolean).join(' · ')}
                    </p>
                  )}
                  {Array.isArray(job.highlights) && job.highlights.length > 0 && (
                    <ul className="item__bullets">
                      {job.highlights.map((point, pointIndex) => (
                        <li key={`${point}-${pointIndex}`}>{point}</li>
                      ))}
                    </ul>
                  )}
                </article>
              ))}
            </div>
          </section>
        )}

        {education.length > 0 && (
          <section className="card section-card">
            <h2 className="section-title">Formation / Education</h2>
            <div className="item-list">
              {education.map((edu, index) => (
                <article key={`${edu.degree}-${edu.school}-${index}`} className="item">
                  {edu.degree ? <h3 className="item__title">{edu.degree}</h3> : null}
                  {(edu.school || edu.year) && (
                    <p className="item__meta">
                      {[edu.school, edu.year === 'CURRENTLY' ? 'Currently' : edu.year]
                        .filter(Boolean)
                        .join(' · ')}
                    </p>
                  )}
                </article>
              ))}
            </div>
          </section>
        )}

        {languages.length > 0 && (
          <section className="card section-card">
            <h2 className="section-title">Languages</h2>
            <ul className="language-list">
              {languages.map((language, index) => (
                <li key={`${language}-${index}`}>{language}</li>
              ))}
            </ul>
          </section>
        )}

        {skills.length > 0 && (
          <section className="card section-card">
            <h2 className="section-title">Skills</h2>
            <ul className="skill-list">
              {skills.map((skill, index) => (
                <li key={`${skill}-${index}`} className="skill-pill">
                  {skill}
                </li>
              ))}
            </ul>
          </section>
        )}

        {projects.length > 0 && (
          <section className="card section-card">
            <h2 className="section-title">Projects</h2>
            <div className="item-list">
              {projects.map((project, index) => (
                <article key={`${project.title}-${index}`} className="item">
                  {project.title ? <h3 className="item__title">{project.title}</h3> : null}
                  {project.description ? <p>{project.description}</p> : null}
                </article>
              ))}
            </div>
          </section>
        )}
      </div>
    );
  }

  return (
    <div className="app">
      <div className="layout">
        <div className="portfolio">{renderPortfolioContent()}</div>

        <aside id="chat" className="chat-sidebar">
          <div className="chat-panel chat-panel--glow">
            <div className="chat-panel__header">
              <h2>Ask about my background</h2>
              <p>
                AI assistant powered by my resume
                {resumeStatus.loaded && (
                  <span className="chat-panel__status">
                    {' '}
                    · {resumeStatus.source || resumeStatus.filename} ({resumeStatus.word_count} words)
                  </span>
                )}
              </p>
            </div>

            {error && (
              <div className="error-banner error-banner--chat" role="alert">
                {error}
              </div>
            )}

            <div className="messages" aria-live="polite">
              {messages.length === 0 && !isLoading && (
                <p className="empty-state">
                  {resumeStatus.loaded
                    ? 'Ask about my experience, skills, or education.'
                    : 'Assistant unavailable until backend/data/resume.pdf is loaded.'}
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
                  resumeStatus.loaded ? 'Ask about my background…' : 'Assistant unavailable…'
                }
                disabled={isLoading || !resumeStatus.loaded}
              />
              <button
                type="submit"
                className="btn-primary"
                disabled={isLoading || !input.trim() || !resumeStatus.loaded}
              >
                Send
              </button>
            </form>
          </div>
        </aside>
      </div>
    </div>
  );
}
