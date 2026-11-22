# Research deployment security

**Language:** [Русский](SECURITY.md) · **English** · [Қазақша](SECURITY.kk.md)

Docker Compose binds the port to `127.0.0.1` and disables live collection by default. The built-in Python HTTP server is not designed for direct public access. Do not change the port binding to `0.0.0.0` without a secure gateway, HTTPS, authentication, request and resource limits, and monitoring.

Keep `.env`, SQLite, HTML/JSON snapshots, CSV files, and backups outside Git. If a token is exposed, generate a new private `.env` or replace the token and restart the container; the old token will stop working. One shared token per instance is appropriate only for a controlled research environment.

Do not disclose secrets or real listings in a public issue when reporting a vulnerability. Contact the operator of the deployed instance through a private channel. This project does not yet publish a security-report address; until one exists, do not post private data in the repository.
