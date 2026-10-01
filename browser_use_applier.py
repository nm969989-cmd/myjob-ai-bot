# -*- coding: utf-8 -*-
"""
🤖 BROWSER-USE AUTONOMOUS JOB APPLIER
=============================================================================
Leverages the `browser-use` AI agent framework powered by Gemini Vision LLM
to visually navigate, autofill, attach resumes, answer screening questions,
and autonomously submit applications across any ATS or career portal.
"""

import os
import sys
import json
import time
import asyncio
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

load_dotenv(override=True)

try:
    from browser_use.agent.service import Agent
    from browser_use.llm.google import ChatGoogle
    from browser_use.browser.session import BrowserSession
    BROWSER_USE_AVAILABLE = True
except Exception as e:
    BROWSER_USE_AVAILABLE = False
    _IMPORT_ERROR = str(e)


class BrowserUseJobApplier:
    def __init__(
        self,
        profile_path: str = "profile.json",
        resume_path: str = "resume.pdf",
        model_name: str = "gemini-2.5-flash",
        headless: bool = True
    ):
        self.profile_path = profile_path
        self.resume_path = os.path.abspath(resume_path)
        self.model_name = model_name
        self.headless = headless
        self.profile = self._load_profile()
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")

    def _load_profile(self) -> dict:
        """Loads candidate profile data or provides realistic defaults."""
        defaults = {
            "full_name": "S Manoj",
            "first_name": "Manoj",
            "last_name": "S",
            "email": "gokuuchihatamil@gmail.com",
            "phone": "+91 9345027137",
            "location": "Chennai, Tamil Nadu, India",
            "experience_years": "0 (Fresher)",
            "github": "https://github.com/manoj",
            "linkedin": "https://linkedin.com/in/smanoj",
            "portfolio": "https://smanoj.dev",
            "skills": "Python, JavaScript, Playwright, HTML, CSS, SQL, Automation, Git, Web Scraping, AI Integration",
            "about": "Self-motivated fresher software developer with a strong passion for web scraping, browser automation, and AI integrations. Eager to contribute and grow in a fast-paced tech environment.",
            "notice_period": "Immediate",
            "current_salary": "0",
            "expected_salary": "Competitive / As per industry standards"
        }
        if os.path.exists(self.profile_path):
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    defaults.update(data)
            except Exception as e:
                print(f"[BrowserUseApplier] Error loading profile: {e}")
        
        # Ensure first/last name separation
        if "first_name" not in defaults or not defaults["first_name"]:
            parts = defaults.get("full_name", "").split()
            defaults["first_name"] = parts[0] if parts else "Candidate"
            defaults["last_name"] = " ".join(parts[1:]) if len(parts) > 1 else ""

        return defaults

    def _build_task_prompt(self, job_url: str, job_title: str = None, company: str = None) -> str:
        """Constructs an exhaustive, clear task prompt for the AI vision agent."""
        p = self.profile
        resume_file = self.resume_path if os.path.exists(self.resume_path) else "resume.pdf"

        prompt = f"""
You are an expert Autonomous Job Application Agent representing {p.get('full_name')}.
Your goal is to apply for the job opportunity at: {job_url}

Target Role: {job_title or 'Software Engineer / Developer'}
Target Company: {company or 'Hiring Company'}

Candidate Profile Details:
- Full Name: {p.get('full_name')}
- First Name: {p.get('first_name')}
- Last Name: {p.get('last_name')}
- Email: {p.get('email')}
- Phone: {p.get('phone')}
- Location / Address: {p.get('location')}
- LinkedIn: {p.get('linkedin')}
- GitHub: {p.get('github')}
- Portfolio / Website: {p.get('portfolio')}
- Total Experience: {p.get('experience_years')}
- Primary Skills: {p.get('skills')}
- Summary / Cover Letter: {p.get('about')}
- Notice Period: {p.get('notice_period')}
- Current CTC / Salary: {p.get('current_salary')}
- Expected CTC / Salary: {p.get('expected_salary')}

Resume File Path:
{resume_file}

Instructions for the Application:
1. Navigate directly to {job_url}.
2. Look for any 'Apply', 'Apply Now', 'Easy Apply', 'Submit Application', or job application form. Click it.
3. If presented with sign-in or guest application options, choose 'Apply as Guest' or proceed without account creation if possible.
4. Fill in all standard personal details:
   - Full Name, First Name, Last Name
   - Email address, Phone number
   - Current city / location: {p.get('location')}
   - LinkedIn and GitHub URLs
5. When encountering a file upload button or input for 'Resume', 'CV', or 'Curriculum Vitae', upload the resume from:
   {resume_file}
6. Answer screening questions accurately:
   - Are you authorized to work in India? -> Yes
   - Will you now or in the future require visa sponsorship? -> No
   - Notice period? -> Immediate / 0 days
   - Years of experience? -> 0 or 1 year (Fresher)
   - Why do you want to join / describe yourself? -> Provide a concise 2-sentence summary based on the candidate's skills and passion for engineering.
7. Advance through any multi-step forms ('Next', 'Continue', 'Review').
8. When on the final review page, click 'Submit', 'Submit Application', or 'Finish'.
9. Check for the final confirmation message (e.g. 'Application submitted', 'Thank you for applying', or confirmation tick).
10. Once confirmed, conclude with a brief summary of actions taken and final submission status.
"""
        return prompt.strip()

    async def apply_async(
        self,
        job_url: str,
        job_title: str = None,
        company: str = None,
        step_callback = None
    ) -> dict:
        """
        Executes the autonomous browser-use agent on the target job URL.
        """
        if not BROWSER_USE_AVAILABLE:
            return {
                "status": "error",
                "message": f"browser-use library not initialized: {_IMPORT_ERROR}",
                "job_url": job_url
            }

        if not self.gemini_key:
            return {
                "status": "error",
                "message": "GEMINI_API_KEY is not set in environment or .env",
                "job_url": job_url
            }

        start_time = time.time()
        task_prompt = self._build_task_prompt(job_url, job_title, company)
        
        # Ensure screenshots folder exists
        os.makedirs("screenshots", exist_ok=True)
        screenshot_name = f"apply_{int(start_time)}.png"
        screenshot_path = os.path.join("screenshots", screenshot_name)

        print("\n" + "=" * 60)
        print(f"🤖 [BrowserUse] Starting AI Application Agent for: {company or 'Company'} - {job_title or 'Job'}")
        print(f"🔗 URL: {job_url}")
        print("=" * 60)

        # Initialize LLM
        llm = ChatGoogle(
            model=self.model_name,
            api_key=self.gemini_key,
            temperature=0.2
        )

        available_files = [self.resume_path] if os.path.exists(self.resume_path) else []

        step_counter = [0]
        async def on_step(state, output, step_idx):
            step_counter[0] += 1
            thought = getattr(output, "current_state", {}).get("thought", "") if hasattr(output, "current_state") else ""
            print(f"  [Step {step_counter[0]}] {thought[:100]}")
            if step_callback and callable(step_callback):
                try:
                    await step_callback(step_counter[0], thought)
                except Exception:
                    pass

        try:
            agent = Agent(
                task=task_prompt,
                llm=llm,
                use_vision=True,
                available_file_paths=available_files,
                register_new_step_callback=on_step,
                max_actions_per_step=4,
                directly_open_url=True,
                sensitive_data={
                    "email": self.profile.get("email", ""),
                    "phone": self.profile.get("phone", "")
                }
            )

            # Run agent loop
            history = await agent.run(max_steps=18)
            duration = int(time.time() - start_time)

            is_done = history.is_done() if hasattr(history, "is_done") else True
            final_result = history.final_result() if hasattr(history, "final_result") else "Application process concluded."

            # Log to applied jobs
            self._record_applied_job(job_url, job_title or "Software Developer", company or "Company", "Auto-Applied via Browser-Use AI Agent")

            return {
                "status": "success" if is_done else "completed",
                "message": str(final_result),
                "duration_seconds": duration,
                "steps_taken": step_counter[0],
                "job_url": job_url,
                "company": company,
                "role": job_title,
                "screenshot": screenshot_path if os.path.exists(screenshot_path) else None
            }

        except Exception as e:
            print(f"⚠️ [BrowserUse] Execution error: {e}")
            return {
                "status": "error",
                "message": f"Browser-Use execution error: {str(e)}",
                "job_url": job_url,
                "company": company
            }

    def apply_sync(self, job_url: str, job_title: str = None, company: str = None) -> dict:
        """Synchronous wrapper for thread-based execution (Telegram Bot)."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # If already running in another thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(asyncio.run, self.apply_async(job_url, job_title, company)).result()
                return result
        else:
            return loop.run_until_complete(self.apply_async(job_url, job_title, company))

    def _record_applied_job(self, url: str, role: str, company: str, note: str):
        """Persists applied status to both applied_jobs.json and applied_jobs_log.csv."""
        # 1. JSON Persistence
        json_file = "applied_jobs.json"
        try:
            applied_set = set()
            if os.path.exists(json_file):
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        applied_set = set(data)
                    elif isinstance(data, dict):
                        applied_set = set(data.keys())
            applied_set.add(url)
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(list(applied_set), f, indent=2)
        except Exception as e:
            print(f"[BrowserUseApplier] Error updating applied_jobs.json: {e}")

        # 2. CSV Persistence
        csv_file = "applied_jobs_log.csv"
        try:
            import csv
            file_exists = os.path.exists(csv_file)
            with open(csv_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Date", "Job Title", "Company", "Status", "Note"])
                writer.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    role,
                    company,
                    "Applied",
                    note
                ])
        except Exception as e:
            print(f"[BrowserUseApplier] Error updating applied_jobs_log.csv: {e}")


def run_browser_use_apply(job_url: str, job_title: str = None, company: str = None) -> dict:
    """Convenience helper function for importing directly into other modules."""
    applier = BrowserUseJobApplier()
    return applier.apply_sync(job_url, job_title, company)


if __name__ == "__main__":
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://apply.workable.com"
    print(f"Testing Browser-Use Applier on: {test_url}")
    applier = BrowserUseJobApplier()
    res = applier.apply_sync(test_url, "Junior Python Developer", "Tech Solutions")
    print("\nResult:", json.dumps(res, indent=2))
