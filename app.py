"""ATS Lab: local-only resume scanner and recruiter review aid, built with Streamlit."""
import csv
import json
import html
import re
from io import StringIO
import streamlit as st
import pandas as pd
from engine import extract_text, scan_resume, extract_skills
from feedback import recommendations_markdown

st.set_page_config(page_title="ATS Lab | Transparent Resume Match", page_icon="📄", layout="wide")
st.markdown("""
<style>
.block-container {max-width: 1230px; padding-top: 2rem;}
.hero {border:1px solid #dbe4f0;padding:22px 26px;border-radius:18px;background:linear-gradient(120deg,#f8fbff,#eaf1ff);margin-bottom:24px;color:#122342}
.hero h1 {margin:0 0 8px;font-size:36px;letter-spacing:-.8px}
.hero p {margin:0;color:#4d5e76;font-size:15px}
[data-testid="stMetric"] {border:1px solid #e6e9f0;border-radius:12px;padding:14px 16px;background:#fafcff;}
.original-quote {padding:11px 13px;border-radius:9px;background:#f7f8fb;border:1px solid #dde2ea;line-height:1.55;color:#182a46;white-space:pre-wrap;overflow-wrap:anywhere;}
.original-quote mark {background:#ffe8a3;color:#17213b;border-radius:2px;padding:0 2px;}
.st-emphasis {color:#445674;font-size:0.9rem;}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>ATS Lab</h1><p>Explainable resume matching · no external AI calls · no invented employer scores</p></div>', unsafe_allow_html=True)
st.info("**Prototype disclosure:** Scores are heuristic, for guidance only. They are **not** Greenhouse, Jobscan, Workday, or any employer's private scoring output. No application is automatically accepted or rejected.")

with st.sidebar:
    st.header("How this prototype works")
    st.write("1. Extract text from PDFs, DOCX, or TXT")
    st.write("2. Compare identifiable job requirements")
    st.write("3. Score job-language alignment and parsing readiness")
    st.write("4. Explain matched and missing skills")
    st.caption("Local processing while the app runs. No database, analytics, API keys, or third-party resume uploads. On a public hosting service, uploaded files still pass through that host's infrastructure.")

candidate_tab, recruiter_tab, methodology_tab = st.tabs(["📝 Check my resume", "👥 Compare candidate files", "🔎 Scoring methodology"])

with candidate_tab:
    st.subheader("Job-specific resume check")
    left, right = st.columns(2, gap="large")
    with left:
        resume_file = st.file_uploader("Upload resume", type=["pdf", "docx", "txt"], key="single", help="PDF, DOCX, TXT; max 15 MB")
        pasted_resume = st.text_area("Or paste the resume text", height=160, placeholder="Experience...\nSkills...\nEducation...", key="resume_paste")
    with right:
        title = st.text_input("Target job title (optional)", placeholder="Senior Software Engineer")
        jd = st.text_area("Paste complete job description", height=250, placeholder="Required: Python, FastAPI, PostgreSQL, AWS...", key="job_text")
    if st.button("Analyze resume", type="primary", use_container_width=True):
        try:
            resume = pasted_resume.strip() or (extract_text(resume_file.getvalue(), resume_file.name) if resume_file else "")
            result = scan_resume(resume, jd, title)
        except Exception as exc:
            st.error(str(exc))
        else:
            st.session_state["last_result"] = result
            st.session_state["last_resume"] = resume
    if "last_result" in st.session_state:
        res = st.session_state["last_result"]
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Simulated job match", f"{res.match_score}/100")
        m2.metric("Parsing readiness", f"{res.readiness_score}/100")
        m3.metric("Requirements identified", res.job_skill_count)
        m4.metric("Matched skills", len(res.matched))
        st.caption(f"{res.result_label} · Formula: {res.match_method}")
        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.subheader("Present in resume")
            if res.matched:
                st.write(" · ".join(f"`{x}`" for x in res.matched))
            else:
                st.warning("No recognized target skills found in resume text.")
        with c2:
            st.subheader("Missing from resume text")
            if res.missing:
                st.write(" · ".join(f"`{x}`" for x in res.missing))
                if res.preferred_missing:
                    st.caption("Preferred/bonus in job description: " + ", ".join(res.preferred_missing))
            else:
                st.success("No recognized target skills missing. Verify the strength of supporting evidence.")
        st.subheader("Specific, sentence-level improvements")
        st.caption("Each finding links to a source line or an explicitly undetected section. Rewrites preserve known facts; anything in [brackets] needs your verification.")
        detailed = res.detailed_recommendations
        if detailed:
            sev_counts = {severity: sum(r["severity"] == severity for r in detailed) for severity in ("High", "Medium", "Low")}
            st.write(f"**{len(detailed)} focused recommendations** · {sev_counts['High']} high priority · {sev_counts['Medium']} medium · {sev_counts['Low']} optional")
            filter_col, sort_col = st.columns(2)
            with filter_col:
                severity_filter = st.selectbox("Priority", ["All priorities", "High", "Medium", "Low"], key="severity_filter")
            with sort_col:
                category_filter = st.selectbox("Issue type", ["All types"] + sorted(set(r["category"] for r in detailed)), key="category_filter")
            shown = [r for r in detailed if (severity_filter == "All priorities" or r["severity"] == severity_filter)
                     and (category_filter == "All types" or r["category"] == category_filter)]
            if not shown:
                st.info("No recommendations match these filters.")
            for index, rec in enumerate(shown, 1):
                priority = {"High": "🔴", "Medium": "🟡", "Low": "🔵"}.get(rec["severity"], "ℹ️")
                place = f"Line {rec['line_number']}" if rec['line_number'] is not None else "Location not detected"
                with st.expander(f"{priority} {rec['title']} — {place}", expanded=index <= 3):
                    st.caption(f"{rec['category']} · {rec['section']} · {rec['severity']} priority")
                    st.markdown("**Original resume text**")
                    orig = rec["current_text"]
                    focus = rec["focus_text"]
                    escaped = html.escape(orig)
                    if focus:
                        escaped = re.sub(re.escape(html.escape(focus)),
                                         lambda match: f"<mark>{match.group(0)}</mark>", escaped, count=1, flags=re.I)
                    st.markdown(f'<div class="original-quote">{escaped}</div>', unsafe_allow_html=True)
                    if focus:
                        st.caption(f"Problematic phrase: {focus}")
                    st.markdown(f"**What's wrong:** {rec['problem']}")
                    st.markdown(f"**Why it matters:** {rec['why_it_matters']}")
                    if rec["job_evidence"]:
                        st.markdown(f"**Relevant job requirement (JD line {rec['job_line_number']}):**")
                        st.code(rec["job_evidence"], language=None)
                    st.markdown("**Suggested replacement / example**")
                    st.code(rec["suggested_rewrite"], language=None)
                    st.markdown(f"**Exactly what to do:** {rec['action']}")
                    if rec["needs_verification"]:
                        st.caption("⚠️ Check every bracketed placeholder or qualification against your real experience before applying.")
            st.download_button("⬇️ Download detailed recommendations (Markdown)",
                               recommendations_markdown(detailed), file_name="ats_lab_detailed_feedback.md",
                               mime="text/markdown")
        else:
            st.success("No specific rule-based problems found in this sample. That does not guarantee ATS compatibility or job fit.")
        with st.expander("Short summary of suggestions"):
            for rec in res.suggestions:
                st.write("• " + rec)
        with st.expander("Parsing checks and raw extracted text"):
            st.dataframe(pd.DataFrame([{"Check": k, "Passed": v} for k,v in res.section_checks.items()]),hide_index=True)
            st.text_area("Text seen by the analyzer", st.session_state["last_resume"], height=250)
        st.download_button("Download JSON report", json.dumps(res.to_dict(), indent=2), file_name="ats_lab_report.json", mime="application/json")

with recruiter_tab:
    st.subheader("Recruiter-side comparison (review aid)")
    st.write("Compare files to **job-related criteria**. This view does not reject candidates, assess personality, or validate their claims.")
    batch_files = st.file_uploader("Upload candidate resumes", type=["pdf", "docx", "txt"], accept_multiple_files=True, key="batch")
    batch_title = st.text_input("Role title", placeholder="Backend Engineer", key="batch_title")
    batch_jd = st.text_area("Role requirements / job description", height=170, key="batch_jd")
    if st.button("Compare files", type="primary", use_container_width=True):
        rows, details, errors = [], {}, []
        if not batch_files:
            st.warning("Upload at least one candidate resume.")
        else:
            for f in batch_files[:30]:
                try:
                    body = extract_text(f.getvalue(), f.name)
                    res = scan_resume(body, batch_jd, batch_title)
                    rows.append({
                        "File": f.name,
                        "Text match /100": res.match_score,
                        "Readiness /100": res.readiness_score,
                        "Skills found": len(res.matched),
                        "Requirements recognized": res.job_skill_count,
                        "Missing key terms": ", ".join(sorted(res.missing, key=lambda s: -res.skill_weights[s])[:5]),
                        "Review": "Human review required",
                    })
                    details[f.name] = res.to_dict()
                except Exception as exc:
                    errors.append(f"{f.name}: {exc}")
            st.session_state["batch_rows"] = rows
            st.session_state["batch_details"] = details
            st.session_state["batch_errors"] = errors
    if "batch_rows" in st.session_state:
        rows = st.session_state["batch_rows"]
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.caption("Scores are not rankings of people or predictions of job performance. Compare evidence manually and avoid using the score as a hiring decision.")
            st.download_button("Download CSV comparison", pd.DataFrame(rows).to_csv(index=False), file_name="ats_lab_comparison.csv", mime="text/csv")
            choice = st.selectbox("View a file's evidence breakdown", [r["File"] for r in rows])
            d = st.session_state["batch_details"][choice]
            st.json({k: d[k] for k in ["matched", "missing", "preferred_missing", "detailed_recommendations", "section_checks", "match_method"]})
        for err in st.session_state["batch_errors"]:
            st.warning(err)

with methodology_tab:
    st.subheader("Interpretable, not proprietary")
    st.markdown("""
    **Job match** consists of:
    - **65%** weighted skill and keyword coverage, where job-description lines marked “required” count more than lines marked “preferred.”
    - **25%** contextual vocabulary similarity (TF-IDF cosine; heuristic normalization).
    - **10%** target job-title token overlap, only when a job title was supplied.

    Without a title, weighting changes to **72% skills / 28% context**. If the JD includes none of the prototype's recognized skills, it falls back to contextual overlap.

    **Parsing readiness is separate** and checks whether common section headings, contact information, and enough readable text were extracted. It **does not** reliably detect PDF columns, fonts, graphics, or how any specific ATS vendor parses the same file.

    **Detailed editorial feedback:** Recommendations now identify the line and exact text where possible, highlight weak phrases, explain why they need revision, and offer a grounded example rewrite. Missing skills link to the actual job-description sentence. Bracketed text is **not** a resume claim: replace it only with facts you can substantiate.

    **Known limitations:** Rule-based rewrites cannot infer what you achieved or supply metrics that are absent from your resume; some PDF line breaks may change quoted line numbers. No OCR for image-only PDFs; an incomplete skill dictionary; no verified competencies or years-of-experience inference; non-English terminology may be missed; no prediction of interview odds; no access to employer-specific screening criteria. A missing phrase is a suggestion to review, **not an instruction to invent experience.**

    **Privacy:** Files are processed in memory during the current Streamlit session; no persistent database or external AI requests are implemented. A public deployment must add authentication, transport security, retention controls, accessibility testing, rate limits, and employment-law review before handling real applicant data.
    """)
    st.caption("Independent educational prototype. Not affiliated with or endorsed by Greenhouse, Jobscan, or Workday.")
