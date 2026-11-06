# Security Policy

## Supported Versions
ThinkBuddy provides security updates and fixes for the following releases:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability
The ThinkBuddy engineering team takes the security and privacy of our student and parent data seriously.

If you discover a security vulnerability, please **DO NOT** create a public GitHub issue.
Instead, report it responsibly via one of the following channels:

- **Security Team Email:** `security@thinkbuddy.org`
- **Subject Format:** `[Vulnerability Report] Component - Brief Description`

### Information to Include in Reports
To help us triage and resolve the issue quickly, please include:
- A clear description of the vulnerability and attack vector.
- Step-by-step reproduction instructions, sample payloads, or proof-of-concept scripts.
- Affected endpoints, database tables, or mobile client build variants.
- Your assessment of severity and potential data impact (e.g., student PII, quiz answers, account takeover).

### SLA & Disclosure Commitments
- **Initial Acknowledgment:** Within 24 hours of receipt.
- **Triage & Severity Assessment:** Within 48 hours.
- **Remediation & Patch Deployment:** Within 7 calendar days for Critical/High vulnerabilities.
- **Safe Harbor:** We commit not to pursue legal action against researchers conducting ethical security research in accordance with this policy.

## Architectural Security Invariants
All contributions must adhere to our zero-compromise architectural invariants:
1. **Server Authority (Rules 5 & 6):** Quiz answer keys are never sent to clients prior to submission.
2. **Assessment Isolation (Rule 18):** Assessed quizzes require native hardware enforcement (`FLAG_SECURE`, Play Integrity) and are strictly prohibited on web clients (`WEB_PLATFORM_PRACTICE_ONLY`).
3. **Token Isolation (Rule 17):** Authentication tokens are never stored in browser-accessible client storage (`localStorage`, `sessionStorage`, `IndexedDB`). Web clients use HttpOnly, SameSite, Secure cookies managed via BFF; mobile clients use Android Keystore / iOS Keychain.
4. **Minor Privacy (P07b):** Parental consent is legally required before processing minor student data; immediate processing suspension upon consent withdrawal.
