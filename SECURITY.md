# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.0.x   | :white_check_mark: |
| 1.0.x   | :x:                |

---

## Reporting a Vulnerability

We take the security of **MyJob AI Radar** seriously. If you discover a security vulnerability or sensitive information exposure, please follow these guidelines:

### 1. Private Disclosure
- **Do NOT open a public GitHub issue** to report security vulnerabilities or exposed tokens.
- Please report vulnerabilities directly via GitHub Private Vulnerability Reporting or by contacting the project maintainer.

### 2. What to Include
When reporting a vulnerability, please provide:
- A clear description of the vulnerability.
- Steps to reproduce the issue (proof of concept).
- Potential impact and affected components.

### 3. Response Process
- We will acknowledge receipt of your vulnerability report within 24–48 hours.
- A fix or mitigation will be developed and released promptly.

---

## Best Practices for Deployments

- **Never hardcode secrets**: Store all credentials (`TELEGRAM_TOKEN`, `GEMINI_API_KEY`, etc.) in `.env` files or GitHub/Hugging Face Secrets.
- **Keep `.env` in `.gitignore`**: Ensure local environment configurations are never pushed to public version control.
- **Use Admin Access Control**: Configure `TELEGRAM_CHAT_ID` to restrict bot interactions exclusively to authorized administrator accounts.
