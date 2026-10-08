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

## Existing public-repository exposure

Previously exposed credentials in git history still require revocation/rotation
at the provider; changing the current code is not a revocation. Do not paste
those credentials in issues, pull requests or logs, and do not rewrite history
without a separately approved recovery plan.

Personal resume/contact files and captured login HTML are still tracked. They
were not removed during the in-place upgrade because cleanup can affect saved
profiles and integrations. The owner should review their public visibility,
move private inputs to protected runtime storage, and invalidate any exposed
sessions. Generated graph files and duplicate dashboard variants were also
left intact for a separate cleanup review. No root license was inferred from
the Node subproject's package metadata.
