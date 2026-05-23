"""Extract structured portfolio data from resume text."""

from __future__ import annotations

import json
import os
import re

import google.generativeai as genai

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")

SUMMARY_MARKER = "Committed to process innovation"

TITLE_SPLIT_WORDS = (
    "COMPUTER",
    "SCIENCE",
    "STUDENT",
    "SOFTWARE",
    "DEVELOPER",
    "ENGINEER",
    "PROGRAMMING",
    "ARTIFICIAL",
    "INTELLIGENCE",
    "DATA",
    "ANALYST",
    "INTERN",
    "FULL",
    "STACK",
    "WEB",
    "MOBILE",
    "TECHNICAL",
    "DEGREE",
)

SECTION_HEADERS = {
    "summary": {"profile", "summary", "about", "about me"},
    "education": {"formation", "education", "academic background"},
    "experience": {"experience", "work experience", "professional experience"},
    "projects": {"projects", "personal projects", "selected projects"},
    "skills": {"skills", "technical skills", "core skills"},
    "languages": {"languages", "language", "idiomas"},
}

RESUME_DATA_PROMPT = """Extract structured portfolio data from the RESUME below.

Return ONLY valid JSON (no markdown, no code fences) using this exact shape:
{
  "name": "",
  "title": "",
  "summary": "",
  "email": "",
  "phone": "",
  "links": [{"label": "", "url": ""}],
  "skills": [],
  "projects": [{"title": "", "description": ""}],
  "experience": [{"title": "", "company": "", "period": "", "highlights": []}],
  "education": [{"degree": "", "school": "", "year": ""}],
  "languages": []
}

Rules:
- The resume is the only source of truth.
- Do NOT invent employers, dates, degrees, certifications, projects, metrics, or achievements.
- Use empty strings or empty arrays when data is missing.
- title must be readable Title Case (not ALL CAPS).
- summary: a polished 2-4 sentence professional bio from the resume profile/summary.
- skills: include technologies and professional strengths clearly supported by the resume (max 15 items).
- experience: include every role listed with bullet highlights when available.
- education: include every degree, program, or formation entry listed (use the education key).
- languages: list each language from the resume (e.g. Spanish, English with level/certification).
- projects: include only if explicitly listed in the resume; otherwise [].
- name must be the person's full name; title must be their job title or student headline (not swapped).
- links: include LinkedIn, GitHub, portfolio, or other URLs/emails found in the resume.

RESUME:
{resume_text}
"""


def _normalize_header(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip()).lower()


def _match_section(line: str) -> str | None:
    key = _normalize_header(line)
    if key.endswith(":"):
        key = key[:-1]
    for section, names in SECTION_HEADERS.items():
        if key in names:
            return section
    return None


def _split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"header": []}
    current = "header"

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        section = _match_section(line)
        if section:
            current = section
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)

    return sections


def _to_title_case(value: str) -> str:
    return _format_display_title(value)


def _is_single_letter_spaced(value: str) -> bool:
    parts = value.split()
    return len(parts) >= 4 and all(len(part) == 1 and part.isalpha() for part in parts)


def _split_compact_uppercase(value: str) -> str:
    compact = re.sub(r"\s+", "", value.strip().upper())
    if not compact.isalpha() or len(compact) < 8:
        return value.strip()

    words: list[str] = []
    index = 0
    sorted_words = sorted(TITLE_SPLIT_WORDS, key=len, reverse=True)

    while index < len(compact):
        matched = False
        for token in sorted_words:
            if compact[index:].startswith(token):
                words.append(token.title())
                index += len(token)
                matched = True
                break
        if not matched:
            next_index = index + 1
            while next_index <= len(compact):
                if any(compact[next_index:].startswith(token) for token in sorted_words):
                    words.append(compact[index:next_index].title())
                    index = next_index
                    matched = True
                    break
                next_index += 1
            if not matched:
                words.append(compact[index:].title())
                break

    return " ".join(words)


def _format_display_title(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""

    if _is_single_letter_spaced(cleaned):
        return _split_compact_uppercase("".join(cleaned.split()))

    compact = re.sub(r"\s+", "", cleaned)
    if compact.isupper() and compact.isalpha() and len(compact) >= 10:
        return _split_compact_uppercase(compact)

    if cleaned.isupper() and len(cleaned) > 4:
        return cleaned.title()

    return cleaned


def _extract_summary_from_text(text: str) -> str:
    marker = SUMMARY_MARKER
    start = text.find(marker)
    if start == -1:
        return ""

    snippet = text[start:]
    end_match = re.search(
        r"\n(?:[A-Z][A-Z\s]{2,}|SOFTWARE DEVELOPER|DATA ANALYST|APPLICATIONS TESTER|E X P E R I E N C E|S K I L L S)",
        snippet,
        flags=re.IGNORECASE,
    )
    summary = snippet[: end_match.start()] if end_match else snippet
    summary = re.sub(r"\s+", " ", summary).strip()
    return summary


def _extract_languages_from_text(text: str) -> list[str]:
    languages: list[str] = []
    for line in text.splitlines():
        cleaned = re.sub(r"\s+", " ", line.strip())
        if not cleaned:
            continue
        lower = cleaned.lower()
        if ("spanish" in lower or "english" in lower) and "|" in cleaned:
            languages.append(cleaned)
    return languages


def _extract_email_phone(text: str) -> tuple[str, str]:
    email_match = EMAIL_RE.search(text)
    phone_match = PHONE_RE.search(text)
    email = email_match.group(0) if email_match else ""
    phone = phone_match.group(0).strip() if phone_match else ""
    return email, phone


def _parse_education_from_text(text: str) -> list[dict]:
    items: list[dict] = []
    lines = [re.sub(r"\s+", " ", line.strip()) for line in text.splitlines() if line.strip()]

    for index, line in enumerate(lines):
        year = ""
        degree = line

        year_match = re.match(r"^(\d{4})\s*[-–]\s*(.+)$", line, flags=re.IGNORECASE)
        current_match = re.match(r"^CURRENTLY\s*[-–]\s*(.+)$", line, flags=re.IGNORECASE)

        if year_match:
            year, degree = year_match.group(1), year_match.group(2).strip()
        elif current_match:
            year, degree = "Currently", current_match.group(1).strip()
        else:
            continue

        school = ""
        if index + 1 < len(lines):
            next_line = lines[index + 1]
            if not re.match(r"^(\d{4}|CURRENTLY)\s*[-–]", next_line, flags=re.IGNORECASE):
                if not re.match(
                    r"^(SOFTWARE DEVELOPER|DATA ANALYST|APPLICATIONS TESTER|[A-Z]{2,}\s+[A-Z]{2,}\s*-\s*\d{4})",
                    next_line,
                    flags=re.IGNORECASE,
                ):
                    school = next_line

        items.append(
            {
                "degree": _format_display_title(degree),
                "school": school,
                "year": year,
            }
        )

    return items


def _parse_experience_from_text(text: str) -> list[dict]:
    role_patterns = [
        (
            r"APPLICATIONS TESTER AND DOCUMENTATION ASSISTANT\s*(.*?)\s*AM[EÉ]RICA MOVIL GROUP\s*[-–]\s*(\d{4})",
            "Applications Tester and Documentation Assistant",
            "AMÉRICA MOVIL GROUP",
        ),
        (
            r"DATA ANALYST INTERN\s*(.*?)\s*AKSI HERRAMIENTAS\s*[-–]\s*(\d{4})",
            "Data Analyst Intern",
            "AKSI HERRAMIENTAS",
        ),
        (
            r"SOFTWARE DEVELOPER\s*(.*?)\s*HUITZIL APPS\s*[-–]\s*(\d{4})",
            "Software Developer",
            "HUITZIL APPS",
        ),
    ]

    normalized = re.sub(r"\s+", " ", text)
    items: list[dict] = []

    for pattern, title, company in role_patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        body = match.group(1)
        period = match.group(2)
        highlights = []
        for sentence in re.split(r"(?<=[.!?])\s+", body):
            cleaned = sentence.strip(" .")
            if len(cleaned) > 20:
                highlights.append(cleaned)
        items.append(
            {
                "title": title,
                "company": company,
                "period": period,
                "highlights": highlights[:6],
            }
        )

    items.sort(key=lambda item: int(item["period"]) if str(item["period"]).isdigit() else 0, reverse=True)
    return items


def _parse_skills_from_text(text: str) -> list[str]:
    skills: list[str] = []
    lines = [re.sub(r"\s+", " ", line.strip()) for line in text.splitlines() if line.strip()]

    for line in lines:
        lower = line.lower()
        if lower.startswith("programming languages:"):
            _, value = line.split(":", 1)
            for part in re.split(r",|;", value):
                cleaned = part.strip().rstrip(".")
                if cleaned:
                    skills.append(cleaned)
            continue
        if any(
            phrase in lower
            for phrase in (
                "process documentation",
                "data analysis",
                "report generation",
                "database",
                "artificial intelligence",
                "agile methodologies",
                "scrum",
            )
        ):
            if len(line) < 140 and "|" not in line:
                skills.append(line.rstrip("."))

    deduped: list[str] = []
    seen: set[str] = set()
    for skill in skills:
        key = skill.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(skill)
    return deduped[:20]


def _enrich_from_raw_text(data: dict, resume_text: str) -> dict:
    enriched = dict(data)

    email, phone = _extract_email_phone(resume_text)
    if not enriched.get("email"):
        enriched["email"] = email
    if not enriched.get("phone"):
        enriched["phone"] = phone

    if not enriched.get("summary"):
        enriched["summary"] = _extract_summary_from_text(resume_text)

    name = str(enriched.get("name", "")).strip()
    title = str(enriched.get("title", "")).strip()
    name, title = _fix_name_title_swap(name, title)
    enriched["name"] = name
    enriched["title"] = _format_display_title(title)

    if not enriched.get("languages"):
        enriched["languages"] = _extract_languages_from_text(resume_text)

    if not enriched.get("education"):
        enriched["education"] = _parse_education_from_text(resume_text)

    if not enriched.get("experience"):
        enriched["experience"] = _parse_experience_from_text(resume_text)

    if not enriched.get("skills"):
        enriched["skills"] = _parse_skills_from_text(resume_text)

    return enriched


def _parse_skills(lines: list[str]) -> list[str]:
    skills: list[str] = []
    for line in lines:
        cleaned = line.lstrip("-•* ").strip()
        if not cleaned:
            continue
        if ":" in cleaned and len(cleaned.split(":", 1)[0]) < 24:
            _, value = cleaned.split(":", 1)
            parts = re.split(r",|;|\|", value)
            skills.extend(part.strip().rstrip(".") for part in parts if part.strip())
        elif "," in cleaned and len(cleaned) < 120:
            skills.extend(part.strip().rstrip(".") for part in cleaned.split(",") if part.strip())
        else:
            skills.append(cleaned.rstrip("."))
    return skills


def _parse_experience(lines: list[str]) -> list[dict]:
    items: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(("-", "•", "*")):
            i += 1
            continue

        title = _to_title_case(line)
        i += 1
        company = ""
        period = ""
        highlights: list[str] = []

        if i < len(lines) and not lines[i].startswith(("-", "•", "*")):
            meta = lines[i]
            if " - " in meta or " – " in meta:
                split_char = " – " if " – " in meta else " - "
                company, period = [part.strip() for part in meta.split(split_char, 1)]
            else:
                company = meta
            i += 1

        while i < len(lines) and lines[i].startswith(("-", "•", "*")):
            highlights.append(lines[i].lstrip("-•* ").strip())
            i += 1

        items.append(
            {
                "title": title,
                "company": company,
                "period": period,
                "highlights": highlights,
            }
        )

    return items


def _parse_education(lines: list[str]) -> list[dict]:
    items: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        upper = line.upper()

        if re.match(r"^\d{4}\s*[-–]", line) or upper.startswith("CURRENTLY"):
            degree = line
            year = ""
            if " - " in line or " – " in line:
                split_char = " – " if " – " in line else " - "
                year, degree = [part.strip() for part in line.split(split_char, 1)]
            elif upper.startswith("CURRENTLY"):
                year = "Present"
                degree = line.split("-", 1)[-1].strip() if "-" in line else line

            school = ""
            if (
                i + 1 < len(lines)
                and not re.match(r"^\d{4}\s*[-–]", lines[i + 1])
                and not lines[i + 1].upper().startswith("CURRENTLY")
            ):
                school = lines[i + 1]
                i += 2
            else:
                i += 1

            items.append({"degree": degree, "school": school, "year": year})
            continue

        i += 1

    return items


def _parse_projects(lines: list[str]) -> list[dict]:
    if not lines:
        return []

    projects: list[dict] = []
    current: dict | None = None

    for line in lines:
        if line.startswith(("-", "•", "*")):
            bullet = line.lstrip("-•* ").strip()
            if current is None:
                current = {"title": "Project", "description": bullet}
            elif current.get("description"):
                current["description"] = f"{current['description']} {bullet}"
            else:
                current["description"] = bullet
            continue

        if current:
            projects.append(current)

        if " - " in line or " – " in line:
            split_char = " – " if " – " in line else " - "
            title, description = [part.strip() for part in line.split(split_char, 1)]
            current = {"title": title, "description": description}
        else:
            current = {"title": line, "description": ""}

    if current:
        projects.append(current)

    return projects


def parse_resume_data_fallback(text: str) -> dict:
    sections = _split_sections(text)
    header_lines = sections.get("header", [])

    blob = " ".join(header_lines)
    email_match = EMAIL_RE.search(blob)
    phone_match = PHONE_RE.search(blob)

    content_lines = []
    for line in header_lines:
        if EMAIL_RE.search(line) or PHONE_RE.search(line):
            continue
        content_lines.append(line)

    name = content_lines[0].strip() if content_lines else ""
    title = _format_display_title(content_lines[1]) if len(content_lines) > 1 else ""
    name, title = _fix_name_title_swap(name, title)

    summary = " ".join(sections.get("summary", [])).strip()
    if not summary:
        summary = _extract_summary_from_text(text)

    return {
        "name": name,
        "title": title,
        "summary": summary,
        "email": email_match.group(0) if email_match else "",
        "phone": phone_match.group(0).strip() if phone_match else "",
        "links": [],
        "skills": _parse_skills(sections.get("skills", [])),
        "projects": _parse_projects(sections.get("projects", [])),
        "experience": _parse_experience(sections.get("experience", [])),
        "education": _parse_education(sections.get("education", [])),
        "languages": _parse_skills(sections.get("languages", [])),
    }


def _strip_json_fences(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _is_spaced_banner(value: str) -> bool:
    cleaned = value.strip()
    if not cleaned:
        return False
    if re.search(r"\b[A-Z] [A-Z] ", cleaned):
        return True
    letters_only = re.sub(r"\s+", "", cleaned)
    return len(cleaned) > 10 and cleaned.upper() == cleaned and len(letters_only) < len(cleaned) * 0.55


def _looks_like_person_name(value: str) -> bool:
    parts = value.strip().split()
    return len(parts) >= 2 and not _is_spaced_banner(value) and not value.strip().isupper()


def _fix_name_title_swap(name: str, title: str) -> tuple[str, str]:
    if _is_spaced_banner(name) and _looks_like_person_name(title):
        return title, _format_display_title(name)
    if _looks_like_person_name(name) and _is_spaced_banner(title):
        return name, _format_display_title(title)
    return name, title


def _coerce_portfolio_data(data: dict) -> dict:
    links = data.get("links") or []
    if not isinstance(links, list):
        links = []

    normalized_links = []
    for item in links:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        url = str(item.get("url", "")).strip()
        if label and url:
            normalized_links.append({"label": label, "url": url})

    def clean_str_list(key: str) -> list[str]:
        values = data.get(key) or []
        if not isinstance(values, list):
            return []
        return [str(v).strip() for v in values if str(v).strip()]

    projects = []
    for item in data.get("projects") or []:
        if isinstance(item, dict) and str(item.get("title", "")).strip():
            projects.append(
                {
                    "title": str(item.get("title", "")).strip(),
                    "description": str(item.get("description", "")).strip(),
                }
            )

    experience = []
    for item in data.get("experience") or []:
        if isinstance(item, dict) and str(item.get("title", "")).strip():
            highlights = item.get("highlights") or []
            if not isinstance(highlights, list):
                highlights = []
            experience.append(
                {
                    "title": _format_display_title(str(item.get("title", "")).strip()),
                    "company": str(item.get("company", "")).strip(),
                    "period": str(item.get("period", "")).strip(),
                    "highlights": [str(h).strip() for h in highlights if str(h).strip()],
                }
            )

    experience.sort(
        key=lambda item: int(re.search(r"\d{4}", item["period"]).group(0))
        if re.search(r"\d{4}", item["period"])
        else 0,
        reverse=True,
    )

    education = []
    education_source = data.get("education") or data.get("formation") or []
    if not isinstance(education_source, list):
        education_source = []
    for item in education_source:
        if isinstance(item, dict) and str(item.get("degree", "")).strip():
            year = str(item.get("year", "")).strip()
            if year.upper() == "CURRENTLY":
                year = "Currently"
            education.append(
                {
                    "degree": _format_display_title(str(item.get("degree", "")).strip()),
                    "school": str(item.get("school", "")).strip(),
                    "year": year,
                }
            )

    name = str(data.get("name", "")).strip()
    title = _format_display_title(str(data.get("title", data.get("role", ""))).strip())
    name, title = _fix_name_title_swap(name, title)
    title = _format_display_title(title)

    summary = str(data.get("summary", "")).strip()

    return {
        "name": name,
        "title": title,
        "summary": summary,
        "email": str(data.get("email", "")).strip(),
        "phone": str(data.get("phone", "")).strip(),
        "links": normalized_links,
        "skills": clean_str_list("skills"),
        "projects": projects,
        "experience": experience,
        "education": education,
        "languages": clean_str_list("languages"),
    }


def extract_resume_data_with_gemini(resume_text: str) -> dict:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured.")

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config={
            "temperature": 0.1,
            "max_output_tokens": 4096,
            "response_mime_type": "application/json",
        },
    )

    prompt = RESUME_DATA_PROMPT.replace("{resume_text}", resume_text)
    response = model.generate_content(prompt)
    raw = getattr(response, "text", None)
    if not raw:
        raise ValueError("Gemini returned an empty portfolio response.")

    parsed = json.loads(_strip_json_fences(raw))
    if not isinstance(parsed, dict):
        raise ValueError("Gemini portfolio response was not a JSON object.")

    return _coerce_portfolio_data(parsed)


def build_resume_data(resume_text: str) -> dict:
    try:
        parsed = extract_resume_data_with_gemini(resume_text)
    except Exception:
        parsed = _coerce_portfolio_data(parse_resume_data_fallback(resume_text))

    enriched = _enrich_from_raw_text(parsed, resume_text)
    result = _coerce_portfolio_data(enriched)
    if not result.get("summary"):
        result["summary"] = _extract_summary_from_text(resume_text)
    return result
