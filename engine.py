"""Transparent, local-only ATS-style analysis. Not a replication of employer ATS scores."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from io import BytesIO
from typing import Dict, List, Tuple
import re

# Deliberately limited, inspectable ontology; extend this to match your target market.
SKILLS: Dict[str, Tuple[str, ...]] = {
    "Python": ("python",), "JavaScript": ("javascript", "ecmascript"),
    "TypeScript": ("typescript",), "Java": ("java",),
    "Go": ("golang", "go language", "go programming"),
    "C#": ("c#", "c sharp"), "C++": ("c++",),
    "Rust": ("rust",), "Kotlin": ("kotlin",), "Swift": ("swift",),
    "PHP": ("php",), "Ruby": ("ruby",), "SQL": ("sql",),
    "PostgreSQL": ("postgresql", "postgres"), "MySQL": ("mysql",),
    "MongoDB": ("mongodb",), "Redis": ("redis",), "DynamoDB": ("dynamodb",),
    "React": ("react", "react.js", "reactjs"),
    "Next.js": ("next.js", "nextjs"), "Vue": ("vue", "vue.js", "vuejs"),
    "Angular": ("angular",), "Node.js": ("node.js", "nodejs"),
    "Express": ("express.js", "expressjs"), "NestJS": ("nestjs", "nest.js"),
    "Django": ("django",), "FastAPI": ("fastapi",), "Flask": ("flask",),
    "Spring Boot": ("spring boot",), ".NET": (".net", "dotnet"),
    "ASP.NET": ("asp.net", "asp net"),
    "Rails": ("ruby on rails", "rails framework"), "Laravel": ("laravel",),
    "React Native": ("react native",), "Flutter": ("flutter",),
    "AWS": ("aws", "amazon web services"), "Azure": ("azure",),
    "GCP": ("gcp", "google cloud platform"),
    "Docker": ("docker",), "Kubernetes": ("kubernetes", "k8s"),
    "Terraform": ("terraform",), "Helm": ("helm charts", "helm"),
    "CI/CD": ("ci/cd", "continuous integration", "continuous deployment"),
    "GitHub Actions": ("github actions",), "Jenkins": ("jenkins",),
    "GitLab CI": ("gitlab ci",),
    "REST APIs": ("rest api", "restful api", "restful services"),
    "GraphQL": ("graphql",), "gRPC": ("grpc",),
    "Microservices": ("microservices", "microservice"),
    "Distributed systems": ("distributed systems", "distributed architecture"),
    "System design": ("system design",),
    "Event-driven architecture": ("event-driven", "event driven"),
    "Kafka": ("kafka",), "RabbitMQ": ("rabbitmq",),
    "Elasticsearch": ("elasticsearch",), "OpenSearch": ("opensearch",),
    "Snowflake": ("snowflake",), "Databricks": ("databricks",),
    "Apache Spark": ("apache spark", "pyspark",),
    "Airflow": ("airflow",), "dbt": ("dbt",),
    "Machine learning": ("machine learning",),
    "NLP": ("natural language processing", "nlp"),
    "LLMs": ("large language models", "large language model", "llms", "llm"),
    "RAG": ("retrieval augmented generation", "retrieval-augmented generation", "rag pipeline", "rag systems"),
    "AI agents": ("ai agents", "agentic ai", "agent orchestration"),
    "Prompt engineering": ("prompt engineering",),
    "PyTorch": ("pytorch",), "TensorFlow": ("tensorflow",),
    "LangChain": ("langchain",), "Vector databases": ("vector database", "vector db"),
    "pgvector": ("pgvector",), "Pinecone": ("pinecone",),
    "OpenAI API": ("openai api",),
    "OAuth": ("oauth",), "OIDC": ("oidc", "openid connect"),
    "SSO": ("single sign-on", "single sign on", "sso"), "SAML": ("saml",),
    "HIPAA": ("hipaa",), "SOC 2": ("soc 2", "soc2"),
    "GDPR": ("gdpr",),
    "Unit testing": ("unit testing", "unit tests"),
    "Integration testing": ("integration testing", "integration tests"),
    "Playwright": ("playwright",), "Cypress": ("cypress",),
    "Selenium": ("selenium",), "pytest": ("pytest",), "Jest": ("jest",),
    "Agile": ("agile",), "Scrum": ("scrum",),
    "Technical leadership": ("technical leadership", "tech lead", "engineering lead"),
    "Stakeholder management": ("stakeholder management",),
}

REQUIRED_HINTS = re.compile(r"\b(required|requirements|must have|must-have|essential|minimum qualifications|you need|proficient in|strong experience with)\b", re.I)
PREFERRED_HINTS = re.compile(r"\b(preferred|nice to have|nice-to-have|bonus|plus|desirable)\b", re.I)
SECTIONS = {
    "Experience": r"(?im)^\s*(?:(?:professional|work|relevant|employment)\s+experience|experience|employment history|work history|career history)\s*:?\s*$",
    "Skills": r"(?im)^\s*(?:(?:technical|core)\s+skills|skills|technologies|technical expertise|tech stack|core competencies|technical competencies)\s*:?\s*$",
    "Education": r"(?im)^\s*(?:education|academic background|academic qualifications|educational background|qualifications)\s*:?\s*$",
}

@dataclass
class ScanResult:
    match_score: int | None
    readiness_score: int
    requirement_score: int | None
    context_score: int
    title_score: int | None
    matched: List[str]
    missing: List[str]
    preferred_missing: List[str]
    skill_weights: Dict[str, float]
    section_checks: Dict[str, bool]
    issues: List[str]
    suggestions: List[str]
    detailed_recommendations: List[Dict]
    resume_word_count: int
    job_skill_count: int
    match_method: str
    result_label: str

    def to_dict(self):
        return asdict(self)


def _has_phrase(text: str, phrase: str) -> bool:
    # Avoid accidentally matching Java inside JavaScript, or React inside React Native.
    pattern = r"(?<![\w])" + re.escape(phrase).replace(r"\ ", r"\s+") + r"(?![\w])"
    return bool(re.search(pattern, text, flags=re.I))


def extract_skills(text: str) -> List[str]:
    return sorted([name for name, aliases in SKILLS.items() if any(_has_phrase(text, alias) for alias in aliases)])


def extract_text(uploaded: bytes, filename: str) -> str:
    """Load text from user supplied PDF/DOCX/TXT. No OCR; do not upload anything externally."""
    if len(uploaded) > 15 * 1024 * 1024:
        raise ValueError("File exceeds the 15 MB prototype limit.")
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        import fitz
        doc = fitz.open(stream=uploaded, filetype="pdf")
        try:
            if doc.page_count > 30:
                raise ValueError("PDF exceeds the 30-page prototype limit.")
            return "\n".join(p.get_text("text", sort=True) for p in doc)
        finally:
            doc.close()
    if ext == "docx":
        from docx import Document
        doc = Document(BytesIO(uploaded))
        blocks = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                blocks.append(" | ".join(cell.text for cell in row.cells))
        # Headers and footers may be parsed differently by real ATS vendors.
        for section in doc.sections:
            blocks.extend(p.text for p in section.header.paragraphs)
            blocks.extend(p.text for p in section.footer.paragraphs)
        return "\n".join(blocks)
    if ext == "txt":
        return uploaded.decode("utf-8-sig", errors="replace")
    raise ValueError("Supported formats: PDF, DOCX, and TXT.")


def _job_weights(job_description: str) -> tuple[Dict[str, float], List[str]]:
    found = extract_skills(job_description)
    snippets = re.split(r"[\n\r]+|(?<=[.!?])\s+", job_description)
    weights = {}
    preferred = []
    for skill in found:
        snippets_for_skill = [s for s in snippets if any(_has_phrase(s, a) for a in SKILLS[skill])]
        if any(REQUIRED_HINTS.search(s) for s in snippets_for_skill):
            weights[skill] = 2.0
        elif snippets_for_skill and all(PREFERRED_HINTS.search(s) for s in snippets_for_skill):
            weights[skill] = 0.6
            preferred.append(skill)
        else:
            weights[skill] = 1.0
    return weights, preferred


def _context_score(resume: str, job: str) -> int:
    """Keyword/context overlap, intentionally simple, interpretable, and capped."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    vect = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1, max_features=6000)
    try:
        X = vect.fit_transform([resume, job])
        raw = float(cosine_similarity(X[0], X[1])[0, 0])
    except ValueError:
        return 0
    # The 0.42 normalizer is a heuristic, not a statistical calibration.
    return round(min(100, 100 * raw / 0.42))


def _title_match(resume: str, title: str) -> int | None:
    title = title.strip().lower()
    if not title:
        return None
    ignored = {"senior", "junior", "staff", "principal", "lead", "remote", "ii", "iii", "iv", "and", "the", "for"}
    tokens = [t for t in re.findall(r"[a-z+#.]+", title) if len(t) > 2 and t not in ignored]
    if not tokens:
        return None
    return round(100 * sum(_has_phrase(resume, tok) for tok in tokens) / len(tokens))


def _readiness(text: str) -> tuple[int, Dict[str, bool], List[str]]:
    wc = len(re.findall(r"\b[\w+#.]+\b", text))
    checks = {name: bool(re.search(rx, text)) for name, rx in SECTIONS.items()}
    checks["Email present"] = bool(re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text))
    # Detect near-empty/failed extraction, not résumé length. A genuine one-page
    # resume can be concise and still parse correctly; word count isn't "ATS quality".
    checks["Enough extractable text"] = wc >= 60
    checks["Readable character extraction"] = len(text.strip()) >= 400 and text.count("\ufffd") < 10
    score = (20 * checks["Experience"] + 15 * checks["Skills"] + 15 * checks["Education"] +
             10 * checks["Email present"] + 20 * checks["Enough extractable text"] +
             20 * checks["Readable character extraction"])
    issues = []
    for k, ok in checks.items():
        if not ok:
            issues.append({
                "Experience": "Use a clear 'Experience' section heading.",
                "Skills": "Use a clear 'Skills' or 'Technical Skills' heading.",
                "Education": "Use a clear 'Education' heading.",
                "Email present": "Include an email address in extractable text.",
                "Enough extractable text": "Fewer than 60 words were extracted; compare the extracted text with the original document.",
                "Readable character extraction": "Extracted text is sparse or contains replacement characters; check your PDF encoding.",
            }[k])
    return int(score), checks, issues


def scan_resume(resume_text: str, job_description: str, job_title: str = "") -> ScanResult:
    if not resume_text.strip():
        raise ValueError("No extractable resume text found. Try a text-based DOCX or PDF.")
    if len(job_description.strip()) < 40:
        raise ValueError("Paste a job description containing at least 40 characters.")
    weights, preferred = _job_weights(job_description)
    skills = set(extract_skills(resume_text))
    matched = [s for s in weights if s in skills]
    missing = [s for s in weights if s not in skills]
    preferred_missing = [s for s in missing if s in preferred]
    wc = len(resume_text.split())
    readiness, section_checks, issues = _readiness(resume_text)
    context = _context_score(resume_text, job_description)
    title = _title_match(resume_text, job_title)
    req = None
    if weights:
        req = round(100 * sum(weights[s] for s in matched) / sum(weights.values()))
        if title is None:
            match = round(0.72 * req + 0.28 * context)
            method = "72% weighted stated skills + 28% vocabulary/context overlap"
        else:
            match = round(0.65 * req + 0.25 * context + 0.10 * title)
            method = "65% weighted stated skills + 25% vocabulary/context overlap + 10% job-title token overlap"
    else:
        match = round(context if title is None else 0.85 * context + 0.15 * title)
        method = "No recognized skills found in the job description; vocabulary/context overlap only" + (" and job-title tokens" if title is not None else "")
        issues.append("No skills from this demo's built-in taxonomy appeared in the job post. Scores may be less reliable.")
    suggestions = []
    if missing:
        top_missing = sorted(missing, key=lambda s: -weights[s])[:7]
        suggestions.append("Review these job requirements and include truthful, demonstrable experience where applicable: " + ", ".join(top_missing) + ".")
    if title is not None and title < 60:
        suggestions.append("Make your relevant target role clear in the headline or experience sections, without changing historical job titles.")
    if context < 40:
        suggestions.append("Describe concrete responsibilities and outcomes that align with the job post, using accurate terminology.")
    suggestions.extend(issues[:3])
    if not suggestions:
        suggestions.append("Check whether each matched term is supported by a concrete bullet or project; keyword presence alone is not proof of experience.")
    from feedback import build_detailed_recommendations
    detailed = build_detailed_recommendations(
        resume=resume_text, job=job_description, job_title=job_title,
        missing=missing, matched=matched, weights=weights, checks=section_checks)
    label = "Closer textual alignment" if match >= 75 else "Some alignment" if match >= 50 else "More gaps to review"
    return ScanResult(match, readiness, req, context, title, matched, missing,
                      preferred_missing, weights, section_checks, issues, suggestions,
                      detailed, wc, len(weights), method, label)
