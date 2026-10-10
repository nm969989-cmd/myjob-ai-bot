# -*- coding: utf-8 -*-
"""
Generate an ATS-compliant PDF resume dynamically using profile.json.
Run: python generate_resume.py
"""
import os
import json
from pathlib import Path

def load_profile():
    profile_path = Path("profile.json")
    if profile_path.exists():
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Warning] Could not read profile.json: {e}")
    return {
        "full_name": "Karthik Subramanian",
        "phone": "+91 98401 23456",
        "email": "karthik.subramanian@gmail.com",
        "location": "Chennai, Tamil Nadu",
        "linkedin": "https://linkedin.com/in/karthik-dev",
        "github": "https://github.com/karthik-tn",
        "portfolio": "https://karthik-dev.github.io",
        "about": "Passionate Software Engineer skilled in full-stack web applications, clean architecture, and problem solving. Eager to contribute to innovative tech teams in Tamil Nadu.",
        "skills": "Python, SQL, React, Node.js, REST APIs, Git, Tailwind CSS, Problem Solving",
        "degree": "B.E. Computer Science & Engineering",
        "college": "Anna University (CEG), Chennai",
        "batch": "2025 Batch",
        "cgpa": "8.6 CGPA"
    }

def build_resume():
    profile = load_profile()
    try:
        from fpdf import FPDF
    except ImportError:
        print("[Notice] fpdf2 is not installed in current Python environment.")
        print("Use the web API /api/resume/download to generate your ATS resume PDF instantly!")
        return

    class ResumePDF(FPDF):
        PRIMARY   = (20, 46, 92)     # Navy
        ACCENT    = (31, 115, 191)   # Tech Blue
        TEXT      = (38, 38, 46)     # Dark Charcoal
        MUTED     = (102, 107, 122)  # Gray

        def section_title(self, title):
            self.ln(4)
            self.set_fill_color(*self.PRIMARY)
            self.set_text_color(255, 255, 255)
            self.set_font("Helvetica", "B", 9)
            self.cell(0, 6, f"  {title.upper()}", border=0, fill=True, new_x="LMARGIN", new_y="NEXT")
            self.ln(2)
            self.set_text_color(*self.TEXT)

    pdf = ResumePDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    # Header
    pdf.set_text_color(*ResumePDF.PRIMARY)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 8, profile.get("full_name", "Karthik Subramanian").upper(), align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*ResumePDF.TEXT)
    contact = f"{profile.get('location', 'Chennai, Tamil Nadu')}  |  {profile.get('phone', '')}  |  {profile.get('email', '')}"
    pdf.cell(0, 5, contact, align="C", new_x="LMARGIN", new_y="NEXT")

    links = f"LinkedIn: {profile.get('linkedin', '')}  |  GitHub: {profile.get('github', '')}"
    pdf.set_text_color(*ResumePDF.MUTED)
    pdf.cell(0, 5, links, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Summary
    pdf.section_title("Professional Summary")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*ResumePDF.TEXT)
    pdf.multi_cell(0, 5, profile.get("about", ""))

    # Skills
    pdf.section_title("Technical Skills")
    skills_raw = profile.get("skills", "")
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5, f"Core Technologies: {skills_raw}")

    # Education
    pdf.section_title("Education")
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.cell(0, 5, profile.get("degree", "B.E. Computer Science"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, f"{profile.get('college', 'Anna University')}  |  {profile.get('batch', '2025')}  |  {profile.get('cgpa', '8.6')}", new_x="LMARGIN", new_y="NEXT")

    out_path = "resume.pdf"
    pdf.output(out_path)
    print(f"[OK] Resume generated from profile.json: {out_path}")

if __name__ == "__main__":
    build_resume()
