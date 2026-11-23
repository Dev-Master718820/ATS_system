from engine import scan_resume, extract_skills, extract_text

def test_skills_boundary():
    assert "JavaScript" in extract_skills("JavaScript and TypeScript")
    assert "Java" not in extract_skills("JavaScript and TypeScript")
    assert "Go" not in extract_skills("I go to work")

def test_weighted_scanning():
    jd = """Senior Software Engineer. Required: Python and FastAPI. Nice to have: Kubernetes. Build APIs with SQL."""
    cv = """Jane Dev jane@example.com\nExperience\nSenior Software Engineer using Python, FastAPI, SQL.\nSkills\nPython, FastAPI, SQL\nEducation\nBS Computer Science\n""" + "Launched backend services. " * 70
    out = scan_resume(cv, jd, "Senior Software Engineer")
    assert out.match_score is not None
    assert out.readiness_score == 100
    assert "FastAPI" in out.matched
    assert "Kubernetes" in out.missing
    assert "Kubernetes" in out.preferred_missing
    assert out.skill_weights["Python"] == 2.0

def test_missing_text_rejected():
    try:
        scan_resume("", "Python software engineer with AWS cloud design and services")
    except ValueError:
        pass
    else:
        assert False

def test_txt():
    assert extract_text(b"Resume text", "file.txt") == "Resume text"


def test_feedback_quotes_exact_weak_phrase_and_line():
    resume = """Jane Doe
jane@example.com
Summary
Backend engineer.
Skills
Python, FastAPI
Experience
Developer | Demo Co | 2023 - Present
- Participated in design reviews and incident postmortems with teams.
- Improved API performance by tuning Python queries.
Education
BSc Computer Science
"""
    jd = "Senior backend role. Required: Python, FastAPI and Kubernetes for production services."
    out = scan_resume(resume, jd, "Backend Developer")
    vague = next(x for x in out.detailed_recommendations if x["category"] == "Bullet clarity")
    assert vague["line_number"] == 9
    assert vague["focus_text"] == "Participated in"
    assert vague["current_text"] == "Participated in design reviews and incident postmortems with teams."
    assert "[" in vague["suggested_rewrite"]
    assert "incident postmortems" in vague["suggested_rewrite"]
    metric = next(x for x in out.detailed_recommendations if x["category"] == "Impact and evidence")
    assert metric["line_number"] == 10
    assert "[add a verified metric" in metric["suggested_rewrite"]


def test_missing_skill_links_to_actual_job_line():
    resume = """Alex
alex@example.com
Skills
Python, SQL
Experience
- Designed Python APIs.
Education
BSc CS"""
    jd = """Build reliable software.
Required: Python and Kubernetes.
Preferred: Terraform."""
    out = scan_resume(resume, jd)
    k8s = next(x for x in out.detailed_recommendations if "Kubernetes'" in x["title"])
    assert k8s["severity"] == "High"
    assert k8s["job_line_number"] == 2
    assert k8s["job_evidence"] == "Required: Python and Kubernetes."
    assert k8s["needs_verification"]
    assert "[If accurate" in k8s["suggested_rewrite"]


def test_common_headings_accepted_no_generic_section_advice():
    resume = """Alex
alex@example.com
Professional Experience
- Built Python APIs for billing.
Technical Skills
Python, AWS
Academic Qualifications
BSc"""
    jd = "Engineer using Python and AWS to build APIs in cloud environments."
    out = scan_resume(resume, jd)
    assert out.section_checks["Experience"]
    assert out.section_checks["Skills"]
    assert out.section_checks["Education"]
    assert not [x for x in out.detailed_recommendations if x["category"] == "Document structure" and "heading" in x["title"].lower()]


def test_unknown_heading_gets_exact_replace_recommendation():
    resume = """Alex
alex@example.com
My Career
- Built Python APIs.
Skills
Python, AWS
Education
BSc"""
    jd = "Engineer using Python and AWS in backend development environments."
    out = scan_resume(resume, jd)
    entry = next(x for x in out.detailed_recommendations if x["title"] == "Rename this heading to 'Experience'")
    assert entry["current_text"] == "My Career"
    assert entry["focus_text"] == "My Career"
    assert entry["line_number"] == 3
    assert entry["suggested_rewrite"] == "Experience"


def test_pdf_extraction_without_bullet_marker_still_finds_weak_sentence():
    resume = """Jamie
jamie@example.com
Skills
Python
Experience
Software Engineer | Demo | 2024 - Present
Participated in sprint reviews and technical discussions.
Built Python services for the internal dashboard.
Education
Bachelor degree"""
    jd = "Backend development with Python cloud services and software engineering experience."
    out = scan_resume(resume, jd)
    assert any(x["line_number"] == 7 and x["focus_text"] == "Participated in" for x in out.detailed_recommendations)


def test_summary_cliche_and_no_unverified_metrics_added():
    resume = """Jamie
jamie@example.com
Summary
Highly motivated engineer who enjoys various technologies.
Skills
Python
Experience
- Improved Python query performance through indexing.
Education
BS"""
    jd = "Python software engineer for backend development and SQL queries."
    out = scan_resume(resume, jd)
    assert any(x["category"] == "Summary specificity" and x["line_number"] == 4 for x in out.detailed_recommendations)
    assert not any("30%" in x["suggested_rewrite"] or "50%" in x["suggested_rewrite"] for x in out.detailed_recommendations)


def test_markdown_report_includes_source_quote():
    from feedback import recommendations_markdown
    resume = """A
x@y.com
Experience
- Participated in code reviews.
Skills
Python
Education
BS"""
    jd = "Python backend developer writing code reviews and modern API infrastructure."
    out = scan_resume(resume, jd)
    report = recommendations_markdown(out.detailed_recommendations)
    assert "Participated in code reviews." in report
    assert "line 4" in report
    assert "Suggested edit:" in report


def test_missing_skill_points_to_actual_skills_text_after_blank_line():
    resume = """Sam
sam@example.com
Skills

Python, PostgreSQL
Experience
- Built Python backend service.
Education
Bachelor's Degree"""
    jd = """Python backend developer.
Required: Python, Kubernetes and PostgreSQL."""
    out = scan_resume(resume, jd)
    rec = next(x for x in out.detailed_recommendations if "Kubernetes'" in x["title"])
    assert rec["line_number"] == 5
    assert rec["current_text"] == "Python, PostgreSQL"
