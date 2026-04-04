# Finance Backend API

FastAPI + PostgreSQL backend for financial transactions with JWT authentication, role-based access control, soft deletes, rate limiting, Alembic migrations, and analytics dashboards.

## Stack

- FastAPI
- PostgreSQL
- SQLAlchemy 2.0 ORM
- Pydantic v2
- Alembic
- JWT auth with `python-jose`
- Password hashing with `passlib[bcrypt]`
- Pytest

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a PostgreSQL database such as `finance_database`.
4. Create `.env` with your local settings.
5. Run migrations:

```bash
alembic upgrade head
```

6. Start the API:

```bash
uvicorn app.main:app --reload
```

7. Optionally seed sample data after migrations:

```bash
python seed_data.py
```

## Environment Variables

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/finance_database
SECRET_KEY=change-me-to-a-long-random-secret-key-with-32-plus-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
API_V1_PREFIX=/api
PROJECT_NAME=Finance Backend API
```

## Authentication Flow

1. Register a user with `POST /api/auth/register`.
2. Login with `POST /api/auth/login` using `application/x-www-form-urlencoded`.
3. Store the returned bearer token.
4. Send `Authorization: Bearer <token>` on protected requests.
5. Re-authenticate when the token expires.

Public registration always creates `viewer` accounts. Elevated roles must be assigned through admin-only user management.

## API Examples

Register:

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@test.com","password":"Test1234!","full_name":"Test User"}'
```

Login:

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@test.com&password=Test1234!"
```

Read current user:

```bash
curl http://localhost:8000/api/users/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

List transactions:

```bash
curl "http://localhost:8000/api/transactions?page=1&page_size=10&type=expense" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Health check:

```bash
curl http://localhost:8000/health
```

## Roles

- `viewer`: can read only their own transactions and dashboard data.
- `analyst`: can read all active transactions and system-wide dashboard data.
- `admin`: can manage users and perform transaction writes. Dashboard aggregates remain scoped to the admin's own transactions.

## Migrations

The project now uses Alembic instead of runtime `create_all()` calls.

Create a new migration:

```bash
alembic revision --autogenerate -m "describe change"
```

Apply migrations:

```bash
alembic upgrade head
```

Rollback one migration:

```bash
alembic downgrade -1
```

Included migrations:

- `001_initial_schema`
- `002_add_transaction_performance_indexes`

## Rate Limiting

- Public auth endpoints are limited by IP.
- Authenticated endpoints are limited by `user.id`.
- Exceeded limits return `429` with `Retry-After` and `X-RateLimit-*` headers.

## Logging and Observability

- `GET /health` checks API and database availability.
- App startup and shutdown use FastAPI lifespan.
- Structured application logging is initialized in `app/utils/logging.py`.
- Global exception handlers normalize validation and database failure responses.

## Testing

The test suite uses an isolated in-memory SQLite database and overrides the normal database dependency.

Run the full suite:

```bash
pytest -q
```

Run with coverage:

```bash
pytest --cov=app tests/
```

Run a specific file:

```bash
pytest tests/test_auth.py
```

## Security and Validation Notes

- JWTs include `sub`, `user_id`, `role`, and `exp`.
- Token expiry defaults to 30 minutes and is controlled by `ACCESS_TOKEN_EXPIRE_MINUTES`.
- Inactive users receive `401 Unauthorized`.
- Transaction category filtering escapes SQL LIKE wildcards before building `ILIKE` patterns.
- Soft-deleted transactions are excluded from list, detail, and dashboard queries.
- Validation errors return the normalized `422` payload used by the frontend.

## Quality Tooling

Install and run the local quality tools after dependency install:

```bash
ruff check .
mypy app
pre-commit install
pre-commit run --all-files
```

## Troubleshooting

- `alembic upgrade head` fails:
  Check `DATABASE_URL` and confirm PostgreSQL is reachable.
- Login returns `401`:
  Verify the password, confirm the user is active, and ensure the bearer token is not expired.
- `403` on transaction writes:
  Only admins can create, update, or delete transactions.
- `/transactions` total looks wrong:
  Confirm you are on the latest code and migrations; counts now use the same scope as the data query.
- Seed script errors:
  Run migrations first so the schema exists before `python seed_data.py`.

## Notes

- OpenAPI docs are available at `/docs`.
- The API root is `/`, while application routes are mounted under `API_V1_PREFIX` (default `/api`).
