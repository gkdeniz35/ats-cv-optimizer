"""
ATS CV Optimizer - Streamlit Web Application
Uses Groq AI (free) to analyze CVs against Job Descriptions
and provide ATS compatibility scoring and improvement suggestions.
"""

import streamlit as st
from groq import Groq
import json
import re
import io

try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

try:
    from docx import Document
    DOCX_SUPPORT = True
except ImportError:
    DOCX_SUPPORT = False


def parse_pdf(file_bytes: bytes) -> str:
    if not PDF_SUPPORT:
        st.error("pdfplumber is not installed.")
        return ""
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def parse_docx(file_bytes: bytes) -> str:
    if not DOCX_SUPPORT:
        st.error("python-docx is not installed.")
        return ""
    doc = Document(io.BytesIO(file_bytes))
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    return "\n".join(paragraphs)


def extract_text_from_upload(uploaded_file) -> str:
    file_bytes = uploaded_file.read()
    name = uploaded_file.name.lower()
    if name.endswith(".pdf"):
        return parse_pdf(file_bytes)
    elif name.endswith(".docx"):
        return parse_docx(file_bytes)
    else:
        st.error("Unsupported file type.")
        return ""


def build_analysis_prompt(cv_text: str, jd_text: str) -> str:
    return f"""You are an expert ATS (Applicant Tracking System) analyst and career coach.

Analyze the CV below against the provided Job Description and return ONLY a valid JSON object
(no markdown fences, no extra text) with exactly this structure:

{{
  "sections_found": {{
    "experience": true,
    "education": true,
    "skills": true,
    "certifications": false
  }},
  "ats_score": 75,
  "score_breakdown": {{
    "keyword_match": 20,
    "section_structure": 15,
    "bullet_quality": 15,
    "formatting": 12,
    "quantified_achievements": 13
  }},
  "missing_keywords": ["keyword1", "keyword2"],
  "weak_bullets": [
    {{
      "original": "original bullet text",
      "issue": "why it is weak",
      "suggestion": "improved version"
    }}
  ],
  "formatting_issues": ["issue1", "issue2"],
  "keyword_suggestions": ["keyword1", "keyword2"],
  "summary": "2-3 sentence overall assessment",
  "top_improvements": [
    "improvement 1",
    "improvement 2",
    "improvement 3",
    "improvement 4",
    "improvement 5"
  ]
}}

---CV---
{cv_text}

---JOB DESCRIPTION---
{jd_text}
"""


def analyze_cv_with_groq(cv_text: str, jd_text: str, api_key: str) -> dict:
    client = Groq(api_key=api_key)
    prompt = build_analysis_prompt(cv_text, jd_text)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2048,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    result = json.loads(raw)
    return result


def score_color(score: int) -> str:
    if score >= 75:
        return "#2ecc71"
    elif score >= 50:
        return "#f39c12"
    else:
        return "#e74c3c"


def score_label(score: int) -> str:
    if score >= 75:
        return "Strong Match ✅"
    elif score >= 50:
        return "Moderate Match ⚠️"
    else:
        return "Weak Match ❌"


def render_score_gauge(score: int):
    color = score_color(score)
    label = score_label(score)
    filled = int(score / 5)
    empty = 20 - filled
    bar = "█" * filled + "░" * empty
    st.markdown(
        f"<h1 style='color:{color}; font-size:3rem;'>{score}/100</h1>"
        f"<p style='font-family:monospace; letter-spacing:2px; color:{color};'>{bar}</p>"
        f"<p style='font-size:1.2rem;'>{label}</p>",
        unsafe_allow_html=True
    )


def main():
    st.set_page_config(page_title="ATS CV Optimizer", page_icon="📄", layout="wide")

    st.title("📄 ATS CV Optimizer")
    st.caption("Powered by Groq AI (Free) — optimize your CV to pass Applicant Tracking Systems")
    st.divider()

    with st.sidebar:
        st.header("⚙️ Settings")
        api_key = st.text_input(
            "Groq API Key",
            type="password",
            help="Get yours at https://console.groq.com"
        )
        st.markdown("---")
        st.markdown("**How it works:**\n1. Paste or upload your CV\n2. Paste the Job Description\n3. Click Analyze\n4. Review your ATS score & suggestions")

    col_cv, col_jd = st.columns(2)

    with col_cv:
        st.subheader("📋 Your CV")
        input_method = st.radio("Input method", ["Paste text", "Upload file (PDF / DOCX)"], horizontal=True)
        cv_text = ""
        if input_method == "Paste text":
            cv_text = st.text_area("Paste your CV here", height=350, placeholder="John Doe\njohn@email.com\n\nEXPERIENCE\n...")
        else:
            uploaded = st.file_uploader("Upload CV", type=["pdf", "docx"], label_visibility="collapsed")
            if uploaded:
                with st.spinner("Parsing file..."):
                    cv_text = extract_text_from_upload(uploaded)
                if cv_text:
                    st.success(f"Extracted {len(cv_text.split())} words from file.")
                    with st.expander("Preview extracted text"):
                        st.text(cv_text[:2000] + ("..." if len(cv_text) > 2000 else ""))

    with col_jd:
        st.subheader("🎯 Job Description")
        jd_text = st.text_area("Paste the Job Description here", height=350, placeholder="We are looking for a Senior Python Engineer with experience in...")

    st.divider()
    analyze_btn = st.button("🔍 Analyze CV", type="primary", use_container_width=True)

    if analyze_btn:
        if not api_key:
            st.error("Please enter your Groq API key in the sidebar.")
            st.stop()
        if not cv_text.strip():
            st.error("Please provide your CV text or upload a file.")
            st.stop()
        if not jd_text.strip():
            st.error("Please paste the Job Description.")
            st.stop()

        with st.spinner("Analyzing your CV with Groq AI... this may take 10-20 seconds."):
            try:
                result = analyze_cv_with_groq(cv_text, jd_text, api_key)
            except json.JSONDecodeError as e:
                st.error(f"Failed to parse AI response: {e}")
                st.stop()
            except Exception as e:
                st.error(f"Analysis failed: {e}")
                st.stop()

        st.success("Analysis complete!")
        st.divider()
        st.header("📊 ATS Analysis Report")

        r1, r2 = st.columns([1, 2])
        with r1:
            st.subheader("ATS Compatibility Score")
            render_score_gauge(result.get("ats_score", 0))

        with r2:
            st.subheader("Score Breakdown")
            breakdown = result.get("score_breakdown", {})
            breakdown_labels = {
                "keyword_match": "Keyword Match (30)",
                "section_structure": "Section Structure (20)",
                "bullet_quality": "Bullet Quality (20)",
                "formatting": "Formatting (15)",
                "quantified_achievements": "Quantified Achievements (15)"
            }
            for key, label in breakdown_labels.items():
                val = breakdown.get(key, 0)
                max_val = int(re.search(r"\((\d+)\)", label).group(1))
                pct = min(100, int((val / max_val) * 100)) if max_val else 0
                st.write(f"**{label}**: {val}/{max_val}")
                st.progress(pct)

        st.divider()
        st.subheader("📁 CV Sections Detected")
        sections = result.get("sections_found", {})
        s_cols = st.columns(4)
        for i, sec in enumerate(["experience", "education", "skills", "certifications"]):
            s_cols[i].metric(label=sec.capitalize(), value="✅" if sections.get(sec, False) else "❌")

        st.divider()
        st.subheader("🗒️ Summary")
        st.info(result.get("summary", "No summary available."))

        st.subheader("🚀 Top 5 Actionable Improvements")
        for i, tip in enumerate(result.get("top_improvements", []), 1):
            st.markdown(f"**{i}.** {tip}")

        st.divider()
        col_kw, col_fmt = st.columns(2)

        with col_kw:
            st.subheader("🔑 Missing Keywords")
            missing = result.get("missing_keywords", [])
            if missing:
                tags_html = " ".join(
                    f"<span style='background:#fff3cd; border:1px solid #ffc107; border-radius:4px; padding:2px 8px; margin:2px; display:inline-block;'>🏷️ {kw}</span>"
                    for kw in missing
                )
                st.markdown(tags_html, unsafe_allow_html=True)
            else:
                st.success("No critical missing keywords detected.")
            st.markdown("---")
            st.subheader("💡 Keyword Suggestions")
            for kw in result.get("keyword_suggestions", []):
                st.markdown(f"• `{kw}`")

        with col_fmt:
            st.subheader("⚠️ Formatting Issues")
            fmt_issues = result.get("formatting_issues", [])
            if fmt_issues:
                for issue in fmt_issues:
                    st.warning(issue)
            else:
                st.success("No major formatting issues found.")

        st.divider()
        st.subheader("✍️ Weak Bullet Points & Rephrasing Suggestions")
        weak_bullets = result.get("weak_bullets", [])
        if weak_bullets:
            for idx, item in enumerate(weak_bullets, 1):
                with st.expander(f"Bullet {idx}: {item.get('original', '')[:60]}..."):
                    st.markdown(f"**Original:**  \n_{item.get('original', '')}_")
                    st.markdown(f"**Issue:** {item.get('issue', '')}")
                    st.markdown(
                        f"<div style='background:#d4edda; padding:10px; border-radius:6px;'>"
                        f"✅ <strong>Suggested:</strong> {item.get('suggestion', '')}</div>",
                        unsafe_allow_html=True
                    )
        else:
            st.success("No critically weak bullets detected.")

        st.divider()
        st.caption("Analysis generated by Groq AI (LLaMA 3.3 70B). Results are advisory.")


if __name__ == "__main__":
    main()
