# Finance Backend API

FastAPI + PostgreSQL backend for financial transactions with JWT authentication, role-based access control, analytics dashboards, seed data, and assessment-friendly rate limiting.

## Stack

- FastAPI
- PostgreSQL
- SQLAlchemy 2.0 ORM
- Pydantic v2
- JWT auth with `python-jose`
- Password hashing with `passlib[bcrypt]`
- In-memory fixed-window rate limiting for single-instance demos

## Features

- User registration and login
- Roles: `viewer`, `analyst`, `admin`
- User management for admins
- Transaction CRUD with role-based restrictions
- Soft delete for transactions via `is_deleted`
- Dashboard endpoints for summary, category breakdown, trends, and recent activity
- Validation with normalized 422 error responses
- Consistent rate limit headers on protected endpoints
- PostgreSQL persistence through SQLAlchemy

## Project Structure

```text
backend/
|-- app/
|   |-- config.py
|   |-- database.py
|   |-- dependencies.py
|   |-- main.py
|   |-- models/
|   |-- rate_limiting/
|   |-- routers/
|   |-- schemas/
|   `-- services/
|-- .env
|-- requirements.txt
|-- README.md
`-- seed_data.py
```

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a PostgreSQL database such as `finance_database`.
4. Create a `.env` file and add or update values.
5. Start the API:

```bash
uvicorn app.main:app --reload
```

6. Optionally seed sample data:

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

## API Summary

### Authentication

- `POST /api/auth/register`
- `POST /api/auth/login`

### Users

- `GET /api/users/me`
- `GET /api/users`
- `PUT /api/users/{user_id}/role`
- `PUT /api/users/{user_id}/status`

### Transactions

- `POST /api/transactions`
- `GET /api/transactions`
- `GET /api/transactions/{transaction_id}`
- `PUT /api/transactions/{transaction_id}`
- `DELETE /api/transactions/{transaction_id}`

### Dashboard

- `GET /api/dashboard/summary`
- `GET /api/dashboard/category-breakdown`
- `GET /api/dashboard/monthly-trends`
- `GET /api/dashboard/recent`

## Rate Limiting

The API includes a reusable dependency-based rate limiting layer designed to be easy to review in a technical assessment while still reflecting production-minded tradeoffs.

### How It Works

- Public auth endpoints are limited by client IP address.
- Authenticated endpoints are limited by `user.id`.
- If the limiter cannot resolve a user for a user-based rule, it falls back to IP-based keys.
- IP extraction prefers `X-Forwarded-For` and falls back to `request.client.host`.
- Keys use the format `rate:{rule}:ip:{ip}` or `rate:{rule}:user:{user_id}`.
- Middleware attaches `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` headers to rate-limited responses.
- A `429 Too Many Requests` response also includes `Retry-After`.

### Enabled Rules

| Endpoint | Strategy | Limit |
| --- | --- | --- |
| `POST /api/auth/login` | IP | 5 requests per minute |
| `POST /api/auth/register` | IP | 3 requests per minute |
| `GET /api/users/me` | User | 60 requests per minute |
| `GET /api/users` | User | 30 requests per minute |
| `PUT /api/users/{user_id}/role` | User | 10 requests per minute |
| `PUT /api/users/{user_id}/status` | User | 10 requests per minute |
| `POST /api/transactions` | User | 20 requests per minute |
| `GET /api/transactions` | User | 60 requests per minute |
| `GET /api/transactions/{transaction_id}` | User | 60 requests per minute |
| `PUT /api/transactions/{transaction_id}` | User | 20 requests per minute |
| `DELETE /api/transactions/{transaction_id}` | User | 10 requests per minute |
| `GET /api/dashboard/summary` | User | 30 requests per minute |
| `GET /api/dashboard/category-breakdown` | User | 30 requests per minute |
| `GET /api/dashboard/monthly-trends` | User | 30 requests per minute |
| `GET /api/dashboard/recent` | User | 30 requests per minute |

### Integration Pattern

Each limited route declares its own rule through a small dependency factory:

```python
@router.post("/login", response_model=Token)
def login(
    _: Annotated[None, Depends(create_rate_limiter(LOGIN_LIMIT, key_strategy="ip"))],
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> Token:
    ...
```

This keeps the rate limiting configuration close to the route, which makes the rules explicit and easy for reviewers to follow.

### Error Response

When a request exceeds its limit, the API returns `429 Too Many Requests` with this structure:

```json
{
  "detail": {
    "error": "rate_limit_exceeded",
    "message": "Rate limit exceeded: 5 login attempts per minute",
    "retry_after_seconds": 12
  }
}
```

### Testing Rate Limiting

1. Start the API with `uvicorn app.main:app --reload`.
2. Trigger a limited endpoint more times than allowed within one minute.
3. Confirm the API returns `429 Too Many Requests`.
4. Inspect the response headers for `Retry-After` and `X-RateLimit-*`.

Example with PowerShell:

```powershell
for ($i = 1; $i -le 6; $i++) {
    try {
        Invoke-RestMethod `
            -Method Post `
            -Uri "http://127.0.0.1:8000/api/auth/login" `
            -ContentType "application/x-www-form-urlencoded" `
            -Body "username=admin@example.com&password=wrong-password"
    } catch {
        $_.Exception.Response.StatusCode.value__
        $_.ErrorDetails.Message
    }
}
```

For automated tests, the shared storage exposes a `reset()` method so a test can clear counters before using `TestClient`.

## Access Rules

- `viewer`: can read only their own transactions and dashboard data.
- `analyst`: can read all transactions and system-wide dashboards, but cannot create, update, or delete.
- `admin`: full access to users and transactions. Dashboard summary follows the requested spec and returns personal data, while analysts get system-wide data.

## Authentication Notes

- **Bearer JWT only:** `POST /api/auth/login` returns JSON `{ "access_token": "...", "token_type": "bearer" }`. Call protected routes with `Authorization: Bearer <access_token>`. This API does **not** set cookies or HttpOnly session cookies on login.
- **Registration payload:** `POST /api/auth/register` accepts `UserCreate`: `email`, `password`, optional `full_name`, and optional `role` (`viewer`, `analyst`, or `admin`), defaulting to `viewer` if omitted. The server stores the `role` sent in the body when present. That behavior is convenient for demos and local testing; a production API would typically force self-registration to `viewer` and allow only admins to assign elevated roles.

## Assumptions

1. Users cannot deactivate themselves.
2. Transaction dates cannot be in the future.
3. Amounts are positive absolute values.
4. Categories are free text.
5. Deletes are soft deletes and set `is_deleted=true`.
6. Pagination defaults to `page=1` and `page_size=10`.
7. Viewers can only access their own records.
8. Analysts are read-only across system data.
9. Only admins can create, update, or delete transactions.
10. JWT tokens expire after 30 minutes (see `ACCESS_TOKEN_EXPIRE_MINUTES` in settings).
11. Clients authenticate with Bearer tokens only; cookie-based sessions are not implemented.

## Production Considerations

- The current implementation is intentionally in-memory and works only for a single API instance.
- A real deployment should move the counters to Redis using `redis-py`.
- Horizontal scaling requires distributed rate limiting; otherwise each instance enforces its own counters.
- Fixed-window limiting is simple and understandable, but it can allow short bursts at window boundaries.
- The middleware and dependency pattern can stay the same even if the storage backend changes from memory to Redis.

## Tradeoffs and Design Decisions

- The dependency-based approach keeps rate limiting explicit at the route level instead of hiding it behind broad global middleware.
- In-memory storage avoids introducing infrastructure complexity for the assessment.
- The storage is thread-safe for a single-process deployment and has cleanup logic to avoid unbounded growth.
- The request state is used to share user and rate limit metadata between dependencies and middleware without changing route response models.
- No new runtime dependencies were required for rate limiting; test tooling was added separately under `requirements.txt`.

## Testing

The project includes an async pytest suite under `tests/` that uses an isolated in-memory SQLite database. Production PostgreSQL settings are not used during test runs.

### Test Setup

- Test configuration lives in `pytest.ini`.
- Shared fixtures, helpers, seeded users, dependency overrides, and rate-limit resets live in `tests/conftest.py`.
- Tests override `get_db` so every request uses the isolated SQLite session.
- `.env.test` documents the test-specific settings used by the suite.

### Install Test Dependencies

```bash
pip install -r requirements.txt
```

### Run Tests

Run the full suite:

```bash
pytest
```

Run a specific file:

```bash
pytest tests/test_auth.py
```

Run a single test:

```bash
pytest tests/test_auth.py::test_register_success_creates_user
```

Run with coverage:

```bash
pytest --cov=app tests/
```

### Security Scanning

The backend has been scanned with Bandit against `app/` and `seed_data.py`.

Example command:

```bash
python -m bandit -r app seed_data.py -f txt
```

At the time of the last scan, Bandit reported no medium- or high-severity findings in the backend application code. This is a useful baseline, but it should not be treated as a guarantee that the system is fully secure for every deployment. Production use still requires proper secret management, environment hardening, dependency maintenance, and ongoing security review.

Show print statements:

```bash
pytest -s
```

Run in verbose mode:

```bash
pytest -v
```

## Manual Test Flow

1. Register or seed `admin`, `analyst`, and `viewer` users.
2. Login via `POST /api/auth/login` using form-data with `username` and `password`.
3. Create transactions as admin.
4. Verify role restrictions:
   - viewer create transaction -> `403`
   - analyst list all transactions -> `200`
   - admin delete transaction -> `204` and the row remains in PostgreSQL with `is_deleted=true`
5. Verify rate limiting:
   - sixth login attempt within one minute from the same IP -> `429`
   - fourth registration attempt within one minute from the same IP -> `429`
   - thirty-first dashboard summary request within one minute for the same user -> `429`
6. Confirm response headers include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, and `Retry-After` on rejected requests.

## Notes

- Tables are auto-created on app startup through SQLAlchemy metadata.
- On startup, the app also ensures the `transactions.is_deleted` column exists for older databases and defaults existing rows to `false`.
- The API uses FastAPI docs at `/docs`.
