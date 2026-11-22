# Deploying a research instance

**Language:** [Русский](../deployment.md) · **English** · [Қазақша](../kk/deployment.md)

## Docker Compose

1. Install Docker with Compose and clone the repository.
2. Run `python scripts/init_env.py`. It creates a private `.env` with a random token, does not print it, and does not overwrite an existing file.
3. Run `docker compose up --build -d`.
4. Check `docker compose ps` and open `http://127.0.0.1:8765/`.

Compose binds the port to the host loopback address. The secret comes from `.env`, which is ignored by Git. The container runs as a non-root user and uses the `krisha_data` volume for SQLite and snapshots. Live collection is off by default. Set `KRISHA_ENABLE_LIVE=1` in `.env` **only after obtaining your own written Kolesa permission**, then run `docker compose up -d --force-recreate`.

If port 8765 is taken, set `KRISHA_HOST_PORT=8766` in `.env` and open `http://127.0.0.1:8766/`. Keep the loopback binding in `compose.yaml`: the local UI is allowed through Docker forwarding for this address and has no separate authentication.

Check the local catalog without exposing the token:

```sh
docker compose exec krisha-list python -m krisha_list stats --db /app/data/krisha.sqlite3
```

The specification is at `http://127.0.0.1:8765/api/v1/openapi.json`. Other `/api/v1` routes require `Authorization: Bearer <token>`. Never put the token in a URL, browser JavaScript, logs, or GitHub issues.

### Data, backups, and updates

The `krisha_data` volume contains `/app/data/krisha.sqlite3` and `/app/data/snapshots/`. `docker compose down` retains the volume; `docker compose down -v` **deletes it**. Before updating, make an SQLite backup:

```sh
docker compose exec -T krisha-list python -c "import sqlite3; s=sqlite3.connect('/app/data/krisha.sqlite3'); d=sqlite3.connect('/app/data/backup.sqlite3'); s.backup(d); d.close(); s.close()"
docker compose cp krisha-list:/app/data/backup.sqlite3 ./backup.sqlite3
```

`backup.sqlite3` contains real data and must stay outside Git. HTML/JSON snapshots may be large; retain or delete them under your own retention policy after backup. Never commit the volume, database dump, snapshots, or `.env` to a public repository.

Update with `git pull` and `docker compose up --build -d`. Check `docker compose logs --tail=100 krisha-list` and the status page.

## Without Docker

Python 3.11+ is required. On Windows PowerShell, from the repository root:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock
.venv\Scripts\python -m pip install --no-deps -e .
.venv\Scripts\python -m krisha_list serve --db data/krisha.sqlite3
```

On Linux/macOS, use `python3 -m venv .venv` and `.venv/bin/python`. Start from the repository root because web assets are in `web/dist`. The local interface is at `http://127.0.0.1:8765/`. For authorized live collection add `--enable-live`. For `/api/v1`, create a separate secret file and pass `--api-token-file`; see [API](api.md).

## Network access

The provided Compose configuration is for one local researcher, not a public Internet service. Network deployment needs an HTTPS gateway, access restrictions, quotas, individual token management, monitoring, and backups. See [SECURITY.md](../../SECURITY.en.md).
