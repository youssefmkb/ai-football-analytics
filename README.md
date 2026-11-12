# ai-football-analytics

AI-assisted football match analysis from video: event timeline, team stats, heatmaps and match reports.

## Repository layout

| Path | Content |
| --- | --- |
| `apps/api` | Backend API (Python, FastAPI, SQLAlchemy, Alembic) |
| `apps/web` | Web application (Next.js, TypeScript, Tailwind CSS) |
| `docker-compose.yml` | Local development stack: PostgreSQL, API, web |
| `.github/workflows` | Continuous integration |

## Run the stack locally

Requirements: Git and Docker Desktop.

```bash
docker compose up --build
```

Then open:

- Web application: http://localhost:3000
- API documentation: http://localhost:8000/docs
- API health check: http://localhost:8000/api/v1/health

The home page shows whether the API and the database are reachable. Both rows should turn green. From there you can create an account, sign in and create your club.

Run `docker compose up --build` again after pulling changes that touch `pyproject.toml` or `package.json`, so the images pick up the new dependencies. Database migrations are applied when the API container starts.

To stop the stack, press `Ctrl+C`, then run `docker compose down`. Add `-v` to also delete the database volume.

To change the database credentials, copy `.env.example` to `.env` and edit it.

## Work on the API without Docker

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

pytest                           # fast run on in-memory SQLite, no service needed
ruff check . && ruff format --check .
uvicorn app.main:app --reload    # needs PostgreSQL, see DATABASE_URL in app/core/config.py
```

The row-level security tests need PostgreSQL and are skipped on SQLite. To run everything, as the CI does, point the tests to an empty database. With the Docker stack running:

```bash
docker compose exec db createdb -U afa afa_test
TEST_DATABASE_URL=postgresql+psycopg://afa:afa@localhost:5432/afa_test pytest
```

Database migrations:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

## Work on the web application without Docker

```bash
cd apps/web
npm install
npm run dev
```

Checks run by the CI: `npm run lint`, `npx tsc --noEmit`, `npm run build`.

## Authentication

- The access token is short-lived (15 minutes) and kept in memory by the web application.
- The refresh token is an `HttpOnly` cookie, stored hashed in the database, rotated on every use and revoked on logout. Replaying an old refresh token ends all sessions of that user.
- The club of a request is always resolved from the token, never from a parameter sent by the client.
- Outside development, the API refuses to start without `SECRET_KEY` and `COOKIE_SECURE=true`.

## Club isolation

Every club-scoped table carries an `organization_id`. Two layers keep clubs apart:

1. Endpoints filter by the caller's club, resolved from the token.
2. PostgreSQL row-level security: club-scoped requests run as the restricted `afa_app` role with `app.current_organization_id` set, so a query that forgets its filter returns nothing from other clubs.

See `apps/api/app/db/tenant.py`. New club-scoped tables must be added to a migration that enables the policy, and endpoints must use the `get_tenant_db` dependency.

## Workflow

- `main` is always deployable. Changes arrive through pull requests.
- Every pull request must pass the CI (API lint and tests, web lint, type check and build).
- Match footage and model weights are never committed.
