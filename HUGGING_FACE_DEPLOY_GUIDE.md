# 🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot)

This guide details how your **Telegram Job Bot** runs 24/7 on **Hugging Face Spaces** (16GB RAM + 2 CPUs free).

Space URL: **https://huggingface.co/spaces/manojprofessional007/myjob-bot**

---

## 🚀 Step 1: Push Code to Hugging Face Space

Your latest clean code has already been pushed to `https://huggingface.co/spaces/manojprofessional007/myjob-bot`.

To deploy future updates with 1 click, simply double-click:
👉 [DEPLOY.bat](file:///d:/insta%20gravity/Telegram_Job_Bot/DEPLOY.bat)

---

## 🔑 Step 2: Configure Space Secrets

Make sure the following secrets are configured inside your Hugging Face Space:

1. Open your Space: **https://huggingface.co/spaces/manojprofessional007/myjob-bot**
2. Click on **Settings** (top-right).
3. Scroll down to **Variables and secrets**.
4. Ensure these secrets exist:

| Secret Name | Value | Description |
| :--- | :--- | :--- |
| `TELEGRAM_TOKEN` | `<YOUR_NEW_BOT_TOKEN>` | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | `<YOUR_TELEGRAM_CHAT_ID>` | Your personal Telegram chat ID |
| `GEMINI_API_KEY` | `AIzaSy...` | Google Gemini API Key |
| `TARGET_CHANNEL` | `JobSkull` | Primary Telegram job channel |
| `GROQ_API_KEY` | `gsk_...` | (Optional) Groq fallback API key |
| `NOTION_API_KEY` | `ntn_...` | (Optional) Notion integration key |
| `NOTION_DATABASE_ID` | `...` | (Optional) Notion Database ID |

---

## ⏰ Step 3: Keep the Bot Online 24/7 (UptimeRobot)

Hugging Face Spaces sleep after idle periods. Keep it awake 24/7 with a free ping:

1. Go to [UptimeRobot.com](https://uptimerobot.com/) and create a free account.
2. Click **Add New Monitor**:
   * **Monitor Type:** `HTTP(s)`
   * **Friendly Name:** `Job Bot HuggingFace`
   * **URL:** `https://manojprofessional007-myjob-bot.hf.space`
   * **Monitoring Interval:** `Every 15 minutes`
3. Click **Create Monitor**.

---

## 📱 Step 4: Verify in Telegram

Open your private chat with **@myjob_autoapply_bot** on Telegram:

1. Send `/start` — Initializes your chat and locks your Chat ID.
2. Send `/status` — Checks server health, AI status, and loaded profile.
3. Send `/radar` — Runs and views multi-platform Job Radar matches.
4. Send `/history` — Views recent job application attempts.
5. Send `/help` — Lists all available bot commands.
