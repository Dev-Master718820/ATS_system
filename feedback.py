"""Evidence-linked resume editing recommendations.

Rules intentionally only rewrite text using claims already in the user's resume.
Suggested bracketed placeholders are questions for the user, not asserted facts.
No external AI call, database or employer-specific ATS behavior.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Dict, Iterable, List, Optional, Tuple

from engine import SKILLS, _has_phrase


@dataclass
class Recommendation:
    category: str
    severity: str  # High, Medium, Low
    title: str
    section: str
    line_number: Optional[int]
    current_text: str
    focus_text: str
    problem: str
    why_it_matters: str
    suggested_rewrite: str
    action: str
    job_evidence: str = ""
    job_line_number: Optional[int] = None
    needs_verification: bool = False

    def to_dict(self):
        return asdict(self)


# Used only to locate/anchor recommendations, not to decide whether a resume
# meets an employer requirement. Recognized aliases should not trigger warnings.
SECTION_HEADERS = {
    "Summary": ("summary", "professional summary", "profile", "career profile", "about me"),
    "Experience": ("experience", "professional experience", "work experience", "relevant experience", "employment history", "work history", "career history", "employment experience"),
    "Skills": ("skills", "technical skills", "core skills", "technologies", "technical expertise", "tech stack", "core competencies", "technical competencies"),
    "Education": ("education", "academic background", "academic qualifications", "educational background", "qualifications"),
    "Projects": ("projects", "selected projects", "relevant projects", "personal projects"),
    "Certifications": ("certifications", "certificates", "licenses and certifications"),
}
ALIASES_TO_RENAME = {
    "Experience": ("work background", "professional background", "my career", "employment background", "career journey"),
    "Skills": ("tools i use", "my toolkit", "what i know", "technology toolkit"),
    "Education": ("studies", "my studies", "schools attended"),
}

HEADER_LOOKUP = {alias: group for group, aliases in SECTION_HEADERS.items() for alias in aliases}


def _normalized_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip(" \t:|•-—" )).lower()


def _extract_sections(lines: List[str]) -> Tuple[Dict[str, int], Dict[int, str]]:
    heading_lines: Dict[str, int] = {}
    line_sections: Dict[int, str] = {}
    active = "Header"
    for i, line in enumerate(lines, 1):
        label = HEADER_LOOKUP.get(_normalized_line(line))
        if label:
            active = label
            heading_lines.setdefault(label, i)
        line_sections[i] = active
    return heading_lines, line_sections


def _find_close_heading(lines: List[str], section: str) -> Tuple[int, str] | None:
    for i, line in enumerate(lines, 1):
        if _normalized_line(line) in ALIASES_TO_RENAME.get(section, ()):
            return i, line.strip()
    return None


def _job_excerpt(jd_lines: List[str], skill: str) -> Tuple[str, Optional[int]]:
    aliases = SKILLS.get(skill, (skill,))
    for i, line in enumerate(jd_lines, 1):
        if any(_has_phrase(line, alias) for alias in aliases):
            return line.strip(), i
    return "", None


def _find_skill_occurrence(lines: List[str], skill: str, sections: Dict[int, str], preferred_section: str = "") -> Tuple[int, str, str] | None:
    aliases = SKILLS.get(skill, (skill,))
    hits = [(i, line.strip(), sections[i]) for i, line in enumerate(lines, 1)
            if any(_has_phrase(line, alias) for alias in aliases)]
    if preferred_section:
        hits = sorted(hits, key=lambda item: item[2] != preferred_section)
    return hits[0] if hits else None


def _bullet_items(lines: List[str], sections: Dict[int, str]) -> Iterable[Tuple[int, str]]:
    """Reconstitute wrapped bullet points while retaining starting line number."""
    bullet_prefix = re.compile(r"^\s*(?:[-*•▪◦]|\d{1,2}[.)])\s+")
    action_start = re.compile(
        r"^\s*(?:built|developed|designed|implemented|optimized|improved|reduced|increased|"
        r"managed|maintained|delivered|launched|shipped|automated|created|integrated|"
        r"participated|worked|helped|assisted|responsible|led|collaborated|"
        r"contributed|supported|migrated|deployed|refactored|tested)\b", re.I)
    i = 0
    while i < len(lines):
        line = lines[i]
        number = i + 1
        # Text extraction from some PDFs strips bullet glyphs. Detect both
        # actual bullet prefixes and action-verb sentences in work sections.
        if sections.get(number) not in ("Experience", "Projects"):
            i += 1
            continue
        if not (bullet_prefix.match(line) or action_start.match(line)):
            i += 1
            continue
        fragments = [bullet_prefix.sub("", line).strip()]
        j = i + 1
        while j < len(lines) and sections[j + 1] == sections[number]:
            next_line = lines[j]
            if not next_line.strip() or bullet_prefix.match(next_line) or action_start.match(next_line):
                break
            if _normalized_line(next_line) in HEADER_LOOKUP:
                break
            # Job titles / employer lines normally contain |, dates or end with a colon.
            if re.search(r"(?:\b(?:19|20)\d{2}\b|\s\|\s)", next_line):
                break
            if len(next_line) < 100 and re.search(r"\b(?:engineer|developer|architect|manager|analyst)\b", next_line, re.I):
                break
            fragments.append(next_line.strip())
            j += 1
        full = " ".join(fragments).strip()
        if full:
            yield number, full
        i = j


def _first_match(pattern: str, s: str) -> str:
    m = re.search(pattern, s, re.I)
    return m.group(0) if m else ""


def _reword_weak_bullet(bullet: str, focus: str) -> str:
    """Produce an honest editable example; do not add facts or metrics."""
    new = bullet.strip().rstrip(" .")
    patterns = {
        r"^responsible for\s+": "Handled ",
        r"^worked on\s+": "Contributed to ",
        r"^helped (?:to )?(?:with )?": "Supported ",
        r"^assisted (?:with|in)\s+": "Supported ",
        r"^participated in\s+": "Contributed to ",
        r"^involved in\s+": "Contributed to ",
    }
    for pattern, replacement in patterns.items():
        if re.search(pattern, new, re.I):
            new = re.sub(pattern, replacement, new, count=1, flags=re.I)
            break
    if new:
        new = new[0].upper() + new[1:]
    return new + " by [describe the exact technical action or decision you contributed and its verified outcome]."


def _is_quantified(bullet: str) -> bool:
    return bool(re.search(r"\b\d+(?:[.,]\d+)?\s*(?:%|percent|ms|s\b|seconds?|minutes?|hours?|days?|weeks?|users?|requests?|transactions?|customers?|deployments?|x\b|times\b|\$|k\b|m\b)", bullet, re.I)
                or re.search(r"\$\s*\d+", bullet))


def build_detailed_recommendations(resume: str, job: str, job_title: str,
                                   missing: List[str], matched: List[str],
                                   weights: Dict[str, float],
                                   checks: Dict[str, bool],
                                   limit: int = 25) -> List[Dict]:
    """Return prioritized, traceable edits including line, direct quote, and rationale.

    Output includes only observed issues or non-fabricated improvement options.
    It makes no promise about employer ATS scores or hiring likelihood.
    """
    lines = resume.splitlines()
    jd_lines = job.splitlines()
    headings, line_sections = _extract_sections(lines)
    recommendations: List[Recommendation] = []

    def add(**kwargs):
        recommendations.append(Recommendation(**kwargs))

    # 1. Real section-header gaps. Match broad accepted aliases before warning.
    for section in ("Experience", "Skills", "Education"):
        if section in headings:
            continue
        close = _find_close_heading(lines, section)
        if close:
            n, line = close
            add(category="Document structure", severity="High", title=f"Rename this heading to '{section}'",
                section=section, line_number=n, current_text=line, focus_text=line,
                problem=f"'{line}' is not one of the standard headings recognized by this reviewer.",
                why_it_matters="Explicit, familiar headings make sections easier for both readers and text parsers to interpret; the exact behavior varies by ATS.",
                suggested_rewrite=section,
                action=f"Replace the heading on line {n} without changing the section content.")
        else:
            add(category="Document structure", severity="High", title=f"Make the '{section}' section identifiable",
                section=section, line_number=None, current_text="[No recognizable section heading found]",
                focus_text="", problem=f"The extracted resume text contains no standalone '{section}' heading or recognized equivalent.",
                why_it_matters="The parser cannot confidently identify this section. It may be absent, embedded in an image, or merged with other text during extraction.",
                suggested_rewrite=section,
                action=f"If the section exists, put '{section}' on its own line above the relevant content. If this looks wrong, inspect the raw extracted text for PDF layout problems.")

    # 2. Explain contact and extraction issues with precise, verifiable checks.
    if not checks.get("Email present", True):
        add(category="Document structure", severity="High", title="Add extractable contact email",
            section="Header", line_number=None, current_text="[No email address detected in extracted text]", focus_text="",
            problem="No standard email address appears in the extracted resume.",
            why_it_matters="Recruiters need reliable contact details. Text stored only in an image, shape, or inaccessible header can fail extraction.",
            suggested_rewrite="Email: [your real email address]",
            action="Place your actual email in normal selectable text near your name; never add a fabricated address.", needs_verification=True)
    if not checks.get("Enough extractable text", True) or not checks.get("Readable character extraction", True):
        add(category="Document structure", severity="High", title="Investigate incomplete text extraction",
            section="Entire document", line_number=None,
            current_text=f"[Extracted {len(resume.split())} words; first 180 characters: {resume[:180].strip()!r}]", focus_text="",
            problem="The extracted text is unusually short or contains unreadable characters.",
            why_it_matters="Analysis can miss genuine experience if the source document is an image-based PDF or if text order is damaged.",
            suggested_rewrite="[Export a selectable-text PDF or standard DOCX; keep real resume content unchanged]",
            action="Select/copy several paragraphs in the original file, compare them with the 'Text seen by the analyzer' panel, and export a text-based PDF or DOCX if needed.", needs_verification=True)

    # 3. Job-specific missing skills. Cite actual JD wording, not inferred qualifications.
    for skill in sorted(missing, key=lambda s: (-weights.get(s, 1), s))[:9]:
        jd_excerpt, jd_line = _job_excerpt(jd_lines, skill)
        priority = "High" if weights.get(skill, 1) >= 1.5 else "Low" if weights.get(skill, 1) < 1 else "Medium"
        skills_line = headings.get("Skills")
        if skills_line is not None:
            # If there are blank lines after "Skills", anchor to the actual
            # displayed text rather than guessing the next line number.
            nearby = [(j + 1, lines[j].strip())
                      for j in range(skills_line, min(len(lines), skills_line + 4))
                      if lines[j].strip()]
            location, original = nearby[0] if nearby else (skills_line, lines[skills_line - 1].strip())
        else:
            location = None
            original = "[Skill not found anywhere in extracted resume]"
        add(category="Job requirement", severity=priority, title=f"Job mentions '{skill}', but your resume does not",
            section="Skills / relevant experience", line_number=location,
            current_text=original, focus_text="", problem=f"No recognized reference to '{skill}' appears in the resume text. This does not establish that you lack the skill.",
            why_it_matters="This is a specific requirement or preference stated in the job posting. Showing real evidence helps reviewers assess alignment.",
            suggested_rewrite=f"[If accurate, add '{skill}' to Skills and describe an actual project where you used it; do not invent experience.]",
            action=f"Check whether you genuinely used {skill}. If so, name it in Skills and revise the relevant project bullet to explain what you built, your role, and the verified outcome. Otherwise leave it out.",
            job_evidence=jd_excerpt, job_line_number=jd_line, needs_verification=True)

    # 4. Skills listed but unsupported in experience: targeted, evidence-based advice.
    exp_lines = [(i, line) for i, line in enumerate(lines, 1) if line_sections[i] in ("Experience", "Projects")]
    exp_text = "\n".join(line for _, line in exp_lines)
    count = 0
    for skill in sorted(matched, key=lambda s: -weights.get(s, 1)):
        if count >= 3:
            break
        if any(_has_phrase(exp_text, alias) for alias in SKILLS[skill]):
            continue
        occurrence = _find_skill_occurrence(lines, skill, line_sections, preferred_section="Skills")
        if not occurrence:
            continue
        n, current, section = occurrence
        jd_excerpt, jd_line = _job_excerpt(jd_lines, skill)
        add(category="Evidence of experience", severity="Medium",
            title=f"Support the listed '{skill}' skill with a real example",
            section=section, line_number=n, current_text=current, focus_text=skill,
            problem=f"'{skill}' appears in the resume but is not mentioned in an Experience or Projects entry.",
            why_it_matters="A standalone keyword shows familiarity, not what you personally delivered. A substantiated bullet gives stronger job-relevant evidence.",
            suggested_rewrite=f"[Use an actual experience entry: describe the feature you built with {skill}, your contribution, and a verified result.]",
            action="Do not copy this template as a claim. Update one truthful experience/project bullet only if you can support it.",
            job_evidence=jd_excerpt, job_line_number=jd_line, needs_verification=True)
        count += 1

    # 5. Replace uninformative summary clichés with specific, verifiable details.
    summary_lines = [(i, line.strip()) for i, line in enumerate(lines, 1)
                     if line_sections[i] == "Summary" and i != headings.get("Summary") and line.strip()]
    cliche_pattern = r"\b(?:results[- ]driven|highly motivated|hardworking|passionate|dynamic professional|team player|excellent communication skills|various technologies)\b"
    for n, line in summary_lines[:5]:
        phrase = _first_match(cliche_pattern, line)
        if not phrase:
            continue
        known_skills = [s for s in matched if any(_has_phrase(resume, alias) for alias in SKILLS[s])][:3]
        supported = ", ".join(known_skills) if known_skills else "[your verified, job-relevant technologies]"
        add(category="Summary specificity", severity="Medium",
            title="Replace a generic self-description with evidence",
            section="Summary", line_number=n, current_text=line, focus_text=phrase,
            problem=f"'{phrase}' is generic and does not show what you actually built or which requirements you meet.",
            why_it_matters="A targeted summary establishes role relevance with supported technologies and concrete examples instead of adjectives.",
            suggested_rewrite=f"Software engineer experienced with {supported}; [add one specific achievement supported by your work history].",
            action="Mention only technologies and accomplishments you can back up in Experience or Projects; keep summary to 2–3 sentences.",
            needs_verification=True)
        break

    # 6. Sentence-level editorial feedback with original quote and exact weak phrase.
    weak_pat = r"\b(?:responsible for|worked on|helped|assisted with|assisted in|participated in|involved in|various|multiple tasks|etc\.)\b"
    outcome_pat = r"\b(?:improved|optimized|increased|reduced|decreased|accelerated|boosted|enhanced|cut|lowered|saved)\b"
    generic_pat = r"\b(?:built|developed|created|implemented|maintained|delivered|shipped|managed|worked)\b"
    for n, bullet in _bullet_items(lines, line_sections):
        weak = _first_match(weak_pat, bullet)
        if weak:
            add(category="Bullet clarity", severity="High",
                title="Replace vague participation language with your contribution",
                section=line_sections[n], line_number=n, current_text=bullet, focus_text=weak,
                problem=f"The phrase '{weak}' does not tell the reader what you personally did or owned.",
                why_it_matters="A strong experience bullet identifies your action, the technical artifact, and the impact, rather than just team participation.",
                suggested_rewrite=_reword_weak_bullet(bullet, weak),
                action="Replace the bracketed placeholder with your actual responsibility and observed result; avoid upgrading 'helped' to 'led' unless true.",
                needs_verification=True)
            continue
        outcome = _first_match(outcome_pat, bullet)
        if outcome and not _is_quantified(bullet):
            jd_excerpt = ""
            jd_line = None
            related = [s for s in matched if any(_has_phrase(bullet, alias) for alias in SKILLS[s])]
            if related:
                jd_excerpt, jd_line = _job_excerpt(jd_lines, related[0])
            add(category="Impact and evidence", severity="Medium",
                title="Make this improvement measurable when evidence exists",
                section=line_sections[n], line_number=n, current_text=bullet, focus_text=outcome,
                problem=f"'{outcome}' describes a positive change, but the sentence has no measurable before/after result.",
                why_it_matters="A supported metric or concrete observed result makes the impact clear. Do not add percentages or numbers you cannot verify.",
                suggested_rewrite=bullet.rstrip(" .") + "; [add a verified metric or concrete result if available].",
                action="Specify what changed (latency, error rate, manual work, uptime, users, etc.) only when based on records. Otherwise state the technical result in plain language.",
                job_evidence=jd_excerpt, job_line_number=jd_line, needs_verification=True)
            continue
        if len(bullet.split()) <= 18 and _first_match(generic_pat, bullet) and not _is_quantified(bullet):
            action_verb = _first_match(generic_pat, bullet)
            add(category="Impact and evidence", severity="Low",
                title="Add the product outcome to this short bullet",
                section=line_sections[n], line_number=n, current_text=bullet, focus_text=action_verb,
                problem="This bullet identifies an activity but leaves the scope or actual outcome unclear.",
                why_it_matters="Your relevant technical work is easier to assess when the reader understands what the system enabled or the problem it solved.",
                suggested_rewrite=bullet.rstrip(" .") + " to support [actual product capability or verified operational outcome].",
                action="Replace the bracketed text with a factual outcome. If you have no verified outcome, add the system purpose instead.",
                needs_verification=True)

    # Present higher-priority, more substantive edits first. Within a category, original order is stable.
    severity_order = {"High": 0, "Medium": 1, "Low": 2}
    recommendations.sort(key=lambda r: (severity_order.get(r.severity, 3),
                                        0 if r.category == "Document structure" else 1,
                                        r.line_number if r.line_number is not None else 10**7))
    return [r.to_dict() for r in recommendations[:limit]]


def recommendations_markdown(recommendations: List[Dict]) -> str:
    """Export a portable human-readable review with explicit evidence."""
    out = ["# ATS Lab — detailed resume recommendations", "",
           "These are heuristic editing suggestions, not an employer ATS score. Bracketed examples require your verification.", ""]
    for idx, r in enumerate(recommendations, 1):
        location = f"line {r['line_number']}" if r["line_number"] is not None else "not located"
        out += [f"## {idx}. [{r['severity']}] {r['title']}",
                f"**Area:** {r['section']} · {location}",
                f"**Original:** {r['current_text']}",
                f"**Weak portion:** {r['focus_text'] or 'Not applicable'}",
                f"**Problem:** {r['problem']}",
                f"**Why:** {r['why_it_matters']}",
                f"**Suggested edit:** {r['suggested_rewrite']}",
                f"**Next action:** {r['action']}"]
        if r["job_evidence"]:
            out.append(f"**Job description evidence (line {r['job_line_number']}):** {r['job_evidence']}")
        if r["needs_verification"]:
            out.append("**Verify before applying:** Suggested text contains placeholders or requires evidence.")
        out.append("")
    return "\n".join(out)
