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

# override=False: a real environment variable (CI secret) must always win over a
# stray local .env file, otherwise a developer's checkout silently shadows prod.
load_dotenv(override=False)

try:
    from browser_use.agent.service import Agent
    from browser_use.llm.google import ChatGoogle
    from browser_use.browser.session import BrowserSession
    BROWSER_USE_AVAILABLE = True
    _IMPORT_ERROR = None
except Exception as e:
    BROWSER_USE_AVAILABLE = False
    _IMPORT_ERROR = str(e)

# browser-use is intentionally absent from requirements.txt: it and
# python-jobspy pin incompatible markdownify versions (==1.2.2 vs <0.14), so
# they cannot be installed into the same environment. python-jobspy powers the
# live scrapers, so it wins. Install browser-use separately to enable this file.
BROWSER_USE_INSTALL_HINT = (
    "browser-use is not installed, so the AI applier is disabled.\n"
    "It cannot share an environment with python-jobspy (conflicting markdownify "
    "pins: browser-use wants ==1.2.2, python-jobspy wants <0.14), which is why it is "
    "not in requirements.txt.\n"
    "To enable it, use a separate environment:\n"
    "    python -m venv .venv-applier\n"
    "    .venv-applier/bin/pip install -r requirements.txt\n"
    "    .venv-applier/bin/pip install browser-use\n"
    "then run:  .venv-applier/bin/python browser_use_applier.py <url> --dry-run"
)


class BrowserUseJobApplier:
    def __init__(
        self,
        profile_path: str = "profile.json",
        resume_path: str = "resume.pdf",
        model_name: str = "gemini-2.5-flash",
        headless: bool = True,
        dry_run: bool = False
    ):
        self.profile_path = profile_path
        self.resume_path = os.path.abspath(resume_path)
        self.model_name = model_name
        self.headless = headless
        # dry_run=True navigates and fills the form but is instructed to stop before
        # the final Submit. Without this the agent submits real applications to real
        # employers with no human confirmation and no undo.
        self.dry_run = dry_run
        self.profile = self._load_profile()
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")

    def _load_profile(self) -> dict:
        """Loads candidate profile data from profile.json.

        No personal defaults are baked in. profile.json is .gitignore'd precisely so
        that real contact details never reach a public repo, and this method sends
        whatever is in it to every employer's application form. If it is missing or
        incomplete we fail loudly rather than submitting invented or someone else's
        details.
        """
        required = ("full_name", "email", "phone")
        profile = {}
        if os.path.exists(self.profile_path):
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    profile = json.load(f) or {}
            except Exception as e:
                print(f"[BrowserUseApplier] Error loading profile: {e}")
                profile = {}

        missing = [k for k in required if not str(profile.get(k, "")).strip()]
        if missing:
            raise FileNotFoundError(
                f"[BrowserUseApplier] {self.profile_path} is missing required field(s): "
                f"{', '.join(missing)}. Create it before running an application so the "
                f"agent submits your real details (it is .gitignore'd on purpose)."
            )

        if not profile.get("first_name"):
            parts = str(profile.get("full_name", "")).split()
            profile["first_name"] = parts[0] if parts else "Candidate"
            profile["last_name"] = " ".join(parts[1:]) if len(parts) > 1 else ""
        profile.setdefault("last_name", "")

        return profile

    def _build_task_prompt(self, job_url: str, job_title: str = None, company: str = None) -> str:
        """Constructs an exhaustive, clear task prompt for the AI vision agent."""
        p = self.profile
        resume_file = self.resume_path if os.path.exists(self.resume_path) else "resume.pdf"

        if self.dry_run:
            final_step_instructions = (
                "8. *** DRY RUN — DO NOT SUBMIT. *** You are on the final review page.\n"
                "   Do NOT click Submit, Submit Application, Finish, or any control that "
                "commits the application.\n"
                "   Instead, capture a screenshot of the completed review page and stop.\n"
                "   Then report: the fields you filled, any unanswered required question, "
                "and anything you were unsure about."
            )
        else:
            final_step_instructions = (
                "8. When on the final review page, click 'Submit', 'Submit Application', "
                "or 'Finish'.\n"
                "   Submitting is irreversible — only click after confirming every required "
                "field is filled and correct."
            )

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
{final_step_instructions}
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
                "message": f"browser-use library not initialized: {_IMPORT_ERROR}\n\n{BROWSER_USE_INSTALL_HINT}",
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
        mode = "DRY RUN (will NOT submit)" if self.dry_run else "LIVE APPLY"
        print(f"🤖 [BrowserUse] {mode} — {company or 'Company'} - {job_title or 'Job'}")
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

            # A dry run never submitted anything, so it must not be recorded as applied
            # or the dedup list would suppress the real attempt later.
            if self.dry_run:
                return {
                    "status": "dry_run",
                    "dry_run": True,
                    "submitted": False,
                    "message": str(final_result),
                    "duration_seconds": duration,
                    "steps_taken": step_counter[0],
                    "job_url": job_url,
                    "company": company,
                    "role": job_title,
                    "screenshot": screenshot_path if os.path.exists(screenshot_path) else None
                }

            # Log to applied jobs (shared, lock-protected writer from main.py)
            self._record_applied_job(job_url, job_title or "Software Developer", company or "Company", "Auto-Applied via Browser-Use AI Agent")

            return {
                "status": "success" if is_done else "completed",
                "dry_run": False,
                "submitted": True,
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
                "submitted": False,
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
        """Records an application in the shared dedup list and CSV log.

        Delegates to main.save_applied_job(), which holds file_lock and uses the
        atomic tmp+os.replace write. A local re-implementation here would race with
        it: the bot runs several apply threads, and an unlocked read-modify-write on
        applied_jobs.json drops concurrent updates, which causes duplicate
        applications to the same job.
        """
        try:
            from main import save_applied_job
            save_applied_job(url)
        except Exception as e:
            print(f"[BrowserUseApplier] Error updating applied_jobs.json: {e}")

        # CSV Persistence
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


def run_browser_use_apply(job_url: str, job_title: str = None, company: str = None,
                          dry_run: bool = False) -> dict:
    """Convenience helper function for importing directly into other modules."""
    applier = BrowserUseJobApplier(dry_run=dry_run)
    return applier.apply_sync(job_url, job_title, company)


if __name__ == "__main__":
    import argparse

    _ap = argparse.ArgumentParser(description="Autonomous job applier (browser-use + Gemini Vision)")
    _ap.add_argument("url", help="Job / application URL")
    _ap.add_argument("--role", default=None)
    _ap.add_argument("--company", default=None)
    _ap.add_argument("--dry-run", action="store_true",
                     help="Fill the form but DO NOT submit. Always use this first.")
    _args = _ap.parse_args()

    print(f"Applying to {_args.url} ({'DRY RUN - will not submit' if _args.dry_run else 'LIVE'})")
    _applier = BrowserUseJobApplier(dry_run=_args.dry_run)
    _res = _applier.apply_sync(_args.url, _args.role, _args.company)
    print("\nResult:", json.dumps(_res, indent=2))
