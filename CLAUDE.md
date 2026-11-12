# AI Football Analytics

SaaS web application that turns the video of a football match into a validated event timeline, team statistics, heatmaps and a match report. Guiding principle: **the AI proposes, the coach validates**. Automatic outputs carry a confidence level and a validation status, and only validated or manually entered events feed the statistics.

First target: amateur teams playing 5, 7 or 8-a-side, filmed by a fixed wide-angle camera. Web only for the first version. Native mobile comes after the beta.

## Layout

- `apps/api`: FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16. One modular deployment, no microservices.
- `apps/web`: Next.js (App Router), TypeScript, Tailwind CSS.
- `docker-compose.yml`: local stack (PostgreSQL, API, web).
- `.github/workflows/ci.yml`: runs on every pull request.

## Commands

Whole stack: `docker compose up --build` (web on :3000, API on :8000, docs on :8000/docs).

API, from `apps/api` with the virtualenv active (`pip install -e ".[dev]"`):

- `pytest`: fast run on in-memory SQLite.
- `TEST_DATABASE_URL=postgresql+psycopg://afa:afa@localhost:5432/afa_test pytest`: full run on PostgreSQL, including row-level security tests. This is what the CI runs.
- `ruff check . && ruff format --check .`
- `alembic revision --autogenerate -m "..."` then review the file by hand, `alembic upgrade head`, `alembic check`.

Web, from `apps/web`:

- `npm run lint`, `npx tsc --noEmit`, `npm run build`. All three must pass.

## Rules that must hold

### Club isolation

- Every club-scoped table has a non-null `organization_id` and a row-level security policy, enabled in its migration (see `0002_teams_players_rls.py`).
- Club-scoped endpoints use the `get_tenant_db` dependency and still filter by `membership.organization_id`. Both layers are required.
- The club always comes from the token (`get_current_membership`), never from a path, query or body parameter.
- A resource of another club answers 404, exactly like a missing one.
- Any new club-scoped endpoint gets a test where a second club tries to read and write it.

### Authentication

- Access tokens are short-lived and stay in memory on the web side. Never put a token in `localStorage`.
- Refresh tokens are `HttpOnly` cookies, stored hashed, rotated on every use. The web client deduplicates refresh calls because a parallel refresh looks like a replay and ends every session.
- Writes are limited to club admins and coaches through `require_staff`.

### Data and AI (for the coming milestones)

- Per-frame detections and tracks go to Parquet files in object storage, not to PostgreSQL.
- Every model output stored in the database references the model version that produced it.
- The assistant uses tool calling over analytics functions. It never produces a number that is not in the function results.
- Match footage and model weights are never committed.
- Check the license of any model, library or dataset before adding it. Ultralytics YOLO is AGPL-3.0 and needs an Enterprise license for a closed SaaS. The detector choice is still open (RF-DETR under Apache 2.0 is the alternative) and will be settled by a benchmark on our own footage.

## Conventions

- Code, comments, commit messages, pull requests and this documentation are in English.
- Everything the user reads in the interface is in French: plain and sober, no exclamation marks, no em dashes.
- API: validation with Pydantic schemas in `app/schemas`, one router per resource in `app/api/v1`, errors as `HTTPException` with a short English `detail`. The web app maps status codes to French messages in the component that makes the call.
- Tests assert behaviour through the HTTP API. A change of behaviour comes with a test that fails without it.
- Web: this Next.js version differs from older ones. Read `apps/web/AGENTS.md` and the guides in `node_modules/next/dist/docs/` before using an unfamiliar API. Client components that read the URL (`useParams`, `useSearchParams`) must sit behind a `<Suspense>` boundary, as in `src/app/teams/[id]/page.tsx`.
- Fetch data inside effects with the `.then(setState)` pattern used in `teams-section.tsx`. The lint rule forbids calling a state-setting function directly in an effect.

## Workflow

- `main` is always deployable. Work happens on a branch and arrives through a pull request.
- A pull request states what it does, how to test it, what was verified and what was not.
- The repository owner tests locally and merges. Never push to `main` and never merge on his behalf.
- Keep pull requests small enough to be tested in one or two hours.

## Where the project stands

Milestone 1 (foundation):

- [x] Repository, Docker Compose, CI
- [x] Accounts, sessions, club creation
- [x] Teams and players, row-level security
- [ ] Matches (opponent, date, format, lineup, periods)
- [ ] Invitations and the coach and player roles in the interface

Next milestones: video upload (multipart, resumable), transcoding and player; then timeline, manual annotation, team statistics and match report. Computer vision starts only after a benchmark on real footage shot with a fixed wide-angle camera.
