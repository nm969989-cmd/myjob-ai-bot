# 🚀 GitHub Actions 24/7 Cloud Automation Guide

Your **Telegram Job Bot** runs 24/7 on **GitHub Actions** (16 GB RAM + 4 vCPUs per run) completely for free with **NO credit card required**.

---

## 📌 Repository Information
- **Repository Remote:** `github https://github.com/nm969989-cmd/myjob-ai-bot.git`
- **Workflow File:** `.github/workflows/job_bot.yml`
- **Cloud Runner Entrypoint:** `cloud_runner.py`
- **Schedule:** 3 daily sweeps at 10:00 AM, 5:00 PM, 9:00 PM IST (~20 min/run, 60 min/day total) sized safely for GitHub's 2,000 min/month free tier + 1-click manual trigger (`workflow_dispatch`).

---

## 🔑 Step 1: Set Up Encrypted Secrets on GitHub

1. Open your repository on GitHub:
   👉 **[https://github.com/nm969989-cmd/myjob-ai-bot](https://github.com/nm969989-cmd/myjob-ai-bot)**
2. Click on **Settings** (top navigation bar).
3. On the left sidebar, expand **Secrets and variables** ➔ Click **Actions**.
4. Click the green **New repository secret** button for each secret below:

| Secret Name | Recommended Value | Description |
| :--- | :--- | :--- |
| **`TELEGRAM_TOKEN`** | *Your Telegram Bot Token* | From [@BotFather](https://t.me/BotFather) |
| **`TELEGRAM_CHAT_ID`** | *Your Personal Telegram ID* | Get from [@userinfobot](https://t.me/userinfobot) |
| **`GEMINI_API_KEY`** | *Your Google Gemini API Key* | From [Google AI Studio](https://aistudio.google.com/) |
| **`GROQ_API_KEY`** | *Your Groq API Key* | (Optional) High-speed fallback AI from [Groq Console](https://console.groq.com/) |
| **`TARGET_CHANNEL`** | `jobopenings_india,JobSkull` | Channels to monitor (comma-separated) |
| **`ADZUNA_APP_ID`** | *(Optional)* | For Adzuna India job search API |
| **`ADZUNA_APP_KEY`** | *(Optional)* | For Adzuna India job search API |
| **`NOTION_API_KEY`** | *(Optional)* | For syncing applied jobs to Notion CRM |
| **`NOTION_DATABASE_ID`**| *(Optional)* | Notion Database ID |

> 🔒 **Security Guarantee:** GitHub encrypts secrets using Libsodium sealed boxes. They are never exposed in logs or visible to anyone.

---

## 🚀 Step 2: Push the Enhanced Code to GitHub

Run this command in your local PowerShell terminal:

```bash
cd "D:\insta gravity\Telegram_Job_Bot"
git add .
git commit -m "🚀 Enhanced: Graphify architecture, AI extraction, and GitHub Actions optimizations"
git push github main
```

---

## ⚡ Step 3: Trigger a Manual Test Run in GitHub Actions

1. Go to your repository's **Actions** tab:
   👉 **[https://github.com/nm969989-cmd/myjob-ai-bot/actions](https://github.com/nm969989-cmd/myjob-ai-bot/actions)**
2. In the left sidebar, click **`Telegram Job Bot Cloud Automation`**.
3. Click the **Run workflow** dropdown on the right ➔ click the green **Run workflow** button.
4. Watch the runner:
   - Sets up Python 3.11 with pip cache
   - Restores cached Playwright browser binaries
   - Executes `cloud_runner.py`
   - Scans Job Radar & Telegram channels (`@jobopenings_india`, `@JobSkull`, etc.)
   - Resolves direct apply links & unwraps shorteners (`bit.ly`, `tinyurl`, etc.)
   - Dispatches VIP Job Alert cards with clickable apply buttons to Telegram
   - Auto-commits updated seen job logs back to GitHub (`applied_jobs.json`, `applied_jobs_log.csv`)
5. You will receive real-time job alerts and cycle summary directly on Telegram!
