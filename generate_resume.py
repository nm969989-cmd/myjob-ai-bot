# -*- coding: utf-8 -*-
"""
Generate a professional PDF resume from profile.json using fpdf2.
Run: python generate_resume.py
"""
from fpdf import FPDF

# ─── YOUR PROFILE DATA ────────────────────────────────────────────────────────
NAME          = "S Manoj"
PHONE         = "+91 9345027137"
EMAIL         = "gokuuchihatamil@gmail.com"
LOCATION      = "Bengaluru, Karnataka"
LINKEDIN      = "linkedin.com/in/smanoj"
GITHUB        = "github.com/smanoj"
PORTFOLIO     = "smanoj.dev"

ABOUT = (
    "Self-motivated fresher software developer with a strong passion for web scraping, "
    "browser automation, and AI integrations. Eager to contribute and grow in a fast-paced "
    "tech environment. Quick learner with hands-on experience in building real-world "
    "automation tools and full-stack web applications."
)

SKILLS = [
    "Python", "JavaScript", "HTML & CSS", "SQL",
    "Playwright (Browser Automation)", "Web Scraping (BeautifulSoup)",
    "AI Integration (Gemini API, Groq)", "Git & GitHub",
    "REST APIs", "Flask", "Telegram Bot API", "Linux / Docker"
]

PROJECTS = [
    {
        "name": "Autonomous Job Application Bot",
        "desc": (
            "Built a fully autonomous Telegram bot that scans 11+ job channels, "
            "uses Gemini AI to filter fresher roles, and auto-fills application forms "
            "using Playwright. Deployed 24/7 on Hugging Face Spaces."
        ),
        "tech": "Python, Playwright, Gemini API, Telegram Bot API, Flask"
    },
    {
        "name": "Social Media Auto-Poster",
        "desc": (
            "Developed an automation pipeline that generates AI content and "
            "automatically posts to Instagram, YouTube, and Pinterest using "
            "authenticated browser sessions."
        ),
        "tech": "Python, Playwright, Google APIs, Telegram Bot API"
    },
    {
        "name": "AI News Canvas Generator",
        "desc": (
            "Created a tool that fetches trending news, summarizes it using AI, "
            "and generates visually rich HTML/image canvases for social media."
        ),
        "tech": "Python, HTML, CSS, Gemini API, Pillow"
    }
]

EDUCATION = {
    "degree": "Bachelor of Engineering (B.E.) - Computer Science",
    "college": "Anna University Affiliated College",
    "year": "2024",
    "location": "Tamil Nadu, India"
}

CERTIFICATIONS = [
    "Python for Everybody - Coursera",
    "Web Development Bootcamp - Udemy",
    "Google AI Essentials - Google"
]

# ─── PDF BUILDER ──────────────────────────────────────────────────────────────
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
    print(f"\n[NEXT] Upload resume.pdf to your Hugging Face Space Files tab!")


if __name__ == "__main__":
    build_resume()
