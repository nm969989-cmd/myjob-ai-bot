# -*- coding: utf-8 -*-
"""
Generate an EXAMPLE PDF resume using fpdf2.
Replace every placeholder below with your verified details before using it.
This template does not read profile.json. Keep personal copies private.
Run: python generate_resume.py
"""
from fpdf import FPDF

# Example-only profile: no real person's details or career claims.
NAME = "EXAMPLE - YOUR NAME"
PHONE = "YOUR PHONE"
EMAIL = "you@example.invalid"
LOCATION = "YOUR CITY"
LINKEDIN = "YOUR LINKEDIN URL"
GITHUB = "YOUR GITHUB URL"
PORTFOLIO = "YOUR WEBSITE"
ABOUT = "Replace this example with your own verified professional summary."
SKILLS = ["YOUR VERIFIED SKILL"]
PROJECTS = [{"name": "YOUR VERIFIED PROJECT",
             "desc": "Describe work you actually completed; do not submit this example.",
             "tech": "YOUR PROJECT TECHNOLOGIES"}]
EDUCATION = {"degree": "YOUR DEGREE", "college": "YOUR COLLEGE",
             "year": "YOUR GRADUATION YEAR", "location": "YOUR COLLEGE LOCATION"}
CERTIFICATIONS = ["YOUR VERIFIED CERTIFICATION"]

# PDF builder (unchanged behavior).
class ResumePDF(FPDF):
    PRIMARY   = (30, 30, 60)     # Dark navy
    ACCENT    = (52, 120, 246)   # Blue
    LIGHT     = (245, 247, 250)  # Light gray bg
    TEXT      = (40, 40, 40)     # Dark text
    MUTED     = (110, 110, 130)  # Gray text

    def header(self):
        pass  # Custom header below

    def section_title(self, title):
        self.ln(4)
        self.set_draw_color(*self.ACCENT)
        self.set_fill_color(*self.ACCENT)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 9)
        self.cell(0, 7, f"  {title.upper()}", border=0, fill=True, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
        self.set_text_color(*self.TEXT)

    def bullet(self, text, indent=5):
        self.set_x(self.l_margin + indent)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.TEXT)
        self.cell(4, 5, "*", new_x="RIGHT", new_y="TOP")
        self.multi_cell(0, 5, text)


def build_resume():
    pdf = ResumePDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    # ── HEADER ──────────────────────────────────────────────
    pdf.set_fill_color(*ResumePDF.PRIMARY)
    pdf.rect(0, 0, 210, 38, "F")

    pdf.set_y(8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(0, 10, NAME, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    contact_line = f"{PHONE}  |  {EMAIL}  |  {LOCATION}"
    pdf.cell(0, 6, contact_line, align="C", new_x="LMARGIN", new_y="NEXT")

    link_line = f"LinkedIn: {LINKEDIN}  |  GitHub: {GITHUB}  |  Portfolio: {PORTFOLIO}"
    pdf.cell(0, 6, link_line, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(12)
    pdf.set_text_color(*ResumePDF.TEXT)

    # ── ABOUT ───────────────────────────────────────────────
    pdf.section_title("Professional Summary")
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 5.5, ABOUT)

    # ── SKILLS ──────────────────────────────────────────────
    pdf.section_title("Technical Skills")
    col_w = 90
    skills_left  = SKILLS[:len(SKILLS)//2 + len(SKILLS)%2]
    skills_right = SKILLS[len(SKILLS)//2 + len(SKILLS)%2:]

    x_start = pdf.l_margin
    y_start = pdf.get_y()

    pdf.set_font("Helvetica", "", 9)
    for i, skill in enumerate(skills_left):
        pdf.set_xy(x_start, y_start + i * 5.5)
        pdf.cell(4, 5.5, chr(149))
        pdf.cell(col_w, 5.5, skill)

    for i, skill in enumerate(skills_right):
        pdf.set_xy(x_start + col_w, y_start + i * 5.5)
        pdf.cell(4, 5.5, chr(149))
        pdf.cell(col_w, 5.5, skill)

    pdf.set_y(y_start + max(len(skills_left), len(skills_right)) * 5.5 + 2)

    # ── PROJECTS ────────────────────────────────────────────
    pdf.section_title("Projects")
    for proj in PROJECTS:
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(*ResumePDF.ACCENT)
        pdf.cell(0, 6, proj["name"], new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*ResumePDF.TEXT)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_x(pdf.l_margin + 3)
        pdf.multi_cell(0, 5, proj["desc"])
        pdf.set_font("Helvetica", "I", 8.5)
        pdf.set_text_color(*ResumePDF.MUTED)
        pdf.set_x(pdf.l_margin + 3)
        pdf.cell(0, 5, f"Tech: {proj['tech']}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*ResumePDF.TEXT)
        pdf.ln(2)

    # ── EDUCATION ───────────────────────────────────────────
    pdf.section_title("Education")
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.set_text_color(*ResumePDF.ACCENT)
    pdf.cell(0, 6, EDUCATION["degree"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*ResumePDF.TEXT)
    pdf.cell(0, 5, f"{EDUCATION['college']} - {EDUCATION['location']} | Graduated: {EDUCATION['year']}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # ── CERTIFICATIONS ──────────────────────────────────────
    pdf.section_title("Certifications")
    for cert in CERTIFICATIONS:
        pdf.bullet(cert)
    pdf.ln(2)

    # ── FOOTER ──────────────────────────────────────────────
    pdf.set_y(-12)
    pdf.set_font("Helvetica", "I", 7.5)
    pdf.set_text_color(*ResumePDF.MUTED)
    pdf.cell(0, 5, f"References available upon request  |  {EMAIL}  |  {PHONE}", align="C")

    # Save
    out_path = "resume.pdf"
    pdf.output(out_path)
    import os
    size = os.path.getsize(out_path)
    print(f"[OK] Resume generated: {out_path}")
    print(f"     File size: {size:,} bytes ({size//1024} KB)")
    print("\n[NEXT] Keep resume.pdf on private deployment storage; never commit it to a public repo.")


if __name__ == "__main__":
    build_resume()
