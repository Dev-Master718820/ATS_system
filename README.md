# ATS Lab v2 — evidence-linked ATS-style resume reviewer

**An independent prototype, not a clone of Greenhouse or Jobscan.** It scores **textual alignment** between a resume and job description; it cannot know or predict an employer's private ATS outcome.

## Features

- Candidate-facing resume scanner with a simulated 0–100 job-match score.
- Separate 0–100 extraction/readiness check.
- PDF, DOCX, TXT upload (no OCR for scanned PDFs).
- Job-specific skill dictionary with required vs preferred weights, synonyms, and transparent matched/missing lists.
- Job-title and TF-IDF vocabulary overlap, with formula displayed.
- In-browser recruiter-side comparison of up to 30 files, for **human review only**.
- **NEW: precise, line-level recommendations** with source excerpt, problematic phrase highlighted, why it is weak, proposed rewrite, and next action.
- **NEW: job-posting citations** for missing requirements, including the original JD line.
- **NEW: editable examples with bracketed verification prompts**, never invented metrics, jobs, or credentials.
- **NEW: category/priority filters** in the candidate dashboard.
- **NEW: downloadable Markdown feedback report** along with the JSON report and comparison CSV.
- **NEW: improved section heading recognition** and more sensible handling of short but complete resumes.
- JSON report and CSV comparison download.
- Runs without paid APIs or a database; file content is processed locally by Python server.

## Start locally

```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Then open the local URL Streamlit prints (typically http://localhost:8501).

## Deploy to Streamlit Community Cloud

Create your own GitHub repo with `app.py`, `engine.py`, `requirements.txt`, and `.streamlit/config.toml`. In Streamlit Community Cloud choose this repository and `app.py` as the entrypoint. **Do not deploy with real candidate personal data before adding authentication, privacy and retention controls, and legal/security review.** Public Streamlit hosting means resumes are processed on the hosting server, not solely on the user's device.

## What changed in v2

Replace `app.py` and `engine.py` from v1, and **add** `feedback.py` beside them. The existing `sample_resume.txt`, `sample_job_description.txt`, and `.streamlit/config.toml` still work.

Example from the included demo resume:

> **Location:** Experience, line 18  
> **Original:** Participated in design reviews and incident postmortems with engineering and product teams.  
> **Weak phrase:** “Participated in”  
> **Reason:** Unclear personal contribution.  
> **Proposed rewrite:** Contributed to design reviews and incident postmortems with engineering and product teams by [describe the exact technical action or decision you contributed and its verified outcome].

The matching engine also flags job keywords absent from the resume while quoting the actual job-description line. **Do not insert unmatched skills unless you really have that experience.** Any brackets require verified input from the person whose resume it is.

Line numbers refer to *extracted resume text*, so PDF layout and wrapping can produce different line numbers from the original document. For extraction errors, view “Parsing checks and raw extracted text”. A `100/100` parsing readiness score means only that this prototype's limited checks passed; it does not guarantee compatibility with any ATS.

The new diagnostics are deterministic and rule-based. They can point to vague verbs, weak outcome evidence, unmatched named tools, and ambiguous headings; they do not understand the truth of unrecorded accomplishments or substitute for a human reviewer.

## Scoring model

When recognized job-description skills and a title are present:

```
match = .65 * weighted_skill_coverage + .25 * normalized_TFIDF_similarity + .10 * job_title_token_coverage
```

Without a title: `.72 * skill_coverage + .28 * similarity`.

With no recognized job skills: based on vocabulary overlap alone (and title if supplied). Parsing readiness is a **separate** heuristic based on readable extracted text, common headings and email presence. The short-text threshold is now 60 words rather than 120, to avoid treating a complete concise resume as a PDF extraction failure.

Do not advertise any of these values as Greenhouse, Workday, iCIMS, or Jobscan scores. The skill list is limited; for production-quality international use, add language-specific ontologies, calibrated evaluation data, human-reviewed job requirements, and systematic fairness tests.

## Test

```bash
python -m pytest -q
```

## Next stages for a product

1. Candidate accounts, saved resume revisions, jobs and versioned comparison history.
2. Structured parsing of dates, work experience and education with confidence / provenance rather than guesswork.
3. Improved multi-column PDF interpretation, OCR, contextual competency extraction, and document-format warning system.
4. Human-reviewed weighting/calibration, accessible explanations, manual review and AI opt-out for employer workflows.
5. GDPR/CCPA/security design: consent, access control, encryption, deletion/export, logging, and bias auditing.
6. Real authorized integrations where allowed, using documented employer APIs and user credentials; not reverse engineering vendor scoring logic.

## Privacy and responsibility

This demo makes no external model or tracking calls and stores no resumes in an application database. Streamlit keeps per-session results in memory, and temporary upload data exists on its server while processing. No automated hiring decision or rejection should be based on this tool. Scores are for review and iterative resume improvement.
