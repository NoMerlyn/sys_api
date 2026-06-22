# sys_api — POS Backend (Python + FastAPI)

REST backend for the POS system. Replaces `Proyecto_A/pos-api` (NestJS+Prisma)
with a Python + FastAPI + SQLAlchemy + PostgreSQL stack.

See `openspec/changes/pos-rebuild/` (workspace) for the full design and tasks.

## Stack

- Python 3.12 + FastAPI + uvicorn
- SQLAlchemy 2.x + Alembic (PostgreSQL 15)
- Pydantic v2 + pydantic-settings
- python-jose (JWT) + passlib[bcrypt]
- aio-pika (RabbitMQ client)
- ReportLab (PDF generation)

## Layout

See `openspec/changes/pos-rebuild/design.md` §2.1 for the full directory map.

## Setup (local)

```bash
python -m venv .venv
source .venv/bin/activate     # PowerShell: .venv\Scripts\Activate.ps1
pip install -e .[dev]
cp .env.example .env          # fill in DATABASE_URL, JWT_SECRET, RABBITMQ_URL
alembic upgrade head          # creates schema
python -m app.scripts.seed    # 1k demo seed
uvicorn app.main:app --reload --port 8000
```

## Tests

```bash
pytest -q
```

## Endpoints

Full list in `openspec/changes/pos-rebuild/spec.md` §4.

## Architecture

Clean Architecture: `domain/` (pure entities + value objects), `application/`
(commands/queries/handlers + repository interfaces), `infrastructure/`
(SQLAlchemy + RabbitMQ + PDF + logging), `presentation/` (FastAPI routers).
