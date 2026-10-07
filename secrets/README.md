# Secrets & Credentials Directory

This directory is designated for sensitive credentials, API keys, and environment variables.

> [!CAUTION]
> **NEVER commit sensitive credentials to version control.**
> All files in this directory except `.env.example` and `README.md` are strictly ignored by `.gitignore`.

## Getting Started

1. Copy the example environment file to create your active secrets file:
   ```bash
   cp secrets/.env.example secrets/.env
   # Or create a root symlink if desired:
   ln -s secrets/.env .env
   ```

2. Secure file permissions:
   ```bash
   chmod 600 secrets/.env
   ```

3. Populate your keys and configurations in `secrets/.env`. Both Docker Compose and application configurations automatically load from `secrets/.env`.
