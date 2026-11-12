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

The home page shows whether the API and the database are reachable. Both rows should turn green.

To stop the stack, press `Ctrl+C`, then run `docker compose down`. Add `-v` to also delete the database volume.

To change the database credentials, copy `.env.example` to `.env` and edit it.

## Work on the API without Docker

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

pytest                           # tests, no database needed
ruff check . && ruff format --check .
uvicorn app.main:app --reload    # needs PostgreSQL, see DATABASE_URL in app/core/config.py
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

## Workflow

- `main` is always deployable. Changes arrive through pull requests.
- Every pull request must pass the CI (API lint and tests, web lint, type check and build).
- Match footage and model weights are never committed.
