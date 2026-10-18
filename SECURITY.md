# Security Policy

## Reporting a vulnerability

Please do not open a public issue for security problems. Email `riyannaffanusafara@gmail.com` with a description and steps to reproduce. We will respond as soon as we can.

## Scope and handling of data

scanota processes sales records, which may contain business and customer information.

- This repository contains **synthetic data only**. Do not submit real receipts in issues or pull requests.
- API keys and credentials are read from environment variables and must never be committed. If you find a leaked key, report it so it can be rotated.
- The chat feature converts questions to SQL and executes them with a **read-only database user** limited to `SELECT`.
- Uploaded receipt images should be stored privately and removed when no longer needed.
- The dashboard has no login of its own. When it is reachable from the internet, put authentication and HTTPS in front of it (see "Deploying on a VM" in the README).

## Supported versions

This is a hackathon prototype. Only the latest commit on `main` is supported.