# 🚀 GitHub Actions 24/7 Cloud Automation Guide (Strategy A)

This guide shows how to run your **Telegram Job Bot 24/7 on GitHub Actions** (16 GB RAM + 4 vCPUs per run) completely for free with **NO credit card required**.

---

## 🛠️ Step 1: Create a GitHub Repository

1. Go to **[GitHub.com](https://github.com/new)** and log in.
2. Set:
   * **Repository Name:** `telegram-job-bot`
   * **Visibility:** **Public** (Gives **UNLIMITED free minutes**) or **Private** (Gives 2,000 min/month).
     *(Note: Even on Public repos, your API keys in GitHub Secrets are 100% encrypted & hidden from everyone).*
3. Click **Create repository**.

---

## 🔑 Step 2: Add Encrypted Secrets to Your GitHub Repo

1. In your GitHub repository, click on **Settings** (top menu bar).
2. On the left sidebar, click **Secrets and variables** ➔ **Actions**.
3. Click the green button: **New repository secret**.
4. Add these 4 secrets:

| Secret Name | Value | Description |
| :--- | :--- | :--- |
| **`TELEGRAM_TOKEN`** | `YOUR_BOT_TOKEN` | Telegram Bot Token from @BotFather |
| **`TELEGRAM_CHAT_ID`** | `YOUR_CHAT_ID` | Your Telegram Chat ID |
| **`GEMINI_API_KEY`** | `YOUR_GEMINI_API_KEY` | Google Gemini API Key(s) |
| **`TARGET_CHANNEL`** | `JobSkull` | Telegram Channel to monitor |
| **`GROQ_API_KEY`** | `YOUR_GROQ_API_KEY` | (Optional) Groq fallback AI |

---

## 🚀 Step 3: Push Your Code to GitHub

Open a terminal or run in PowerShell inside `d:\insta gravity\Telegram_Job_Bot`:

```bash
git remote add github https://github.com/YOUR_GITHUB_USERNAME/telegram-job-bot.git
git push -u github main
```

---

## ⚡ Step 4: Run Manually or Let the Schedule Automate

1. In your GitHub repository, click on the **Actions** tab.
2. Select **`Telegram Job Bot Cloud Automation`** on the left.
3. Click **Run workflow** ➔ **Run workflow** (green button).
4. Watch the 16GB runner start up, scan Job Radar & Telegram channels, fill forms, send alerts to Telegram, and finish in ~60 seconds!
5. After this, it will automatically run on schedule every single hour, 24/7/365!
