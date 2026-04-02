# Finance Backend API

FastAPI + PostgreSQL backend for financial transactions with JWT authentication, role-based access control, analytics dashboards, and seed data.

## Stack

- FastAPI
- PostgreSQL
- SQLAlchemy 2.0 ORM
- Pydantic v2
- JWT auth with `python-jose`
- Password hashing with `passlib[bcrypt]`

## Features

- User registration and login
- Roles: `viewer`, `analyst`, `admin`
- User management for admins
- Transaction CRUD with role-based restrictions
- Soft delete for transactions via `is_deleted`
- Dashboard endpoints for summary, category breakdown, trends, and recent activity
- Validation with normalized 422 error responses
- PostgreSQL persistence through SQLAlchemy

## Project Structure

```text
backend/
├── app/
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   ├── main.py
│   ├── models/
│   ├── routers/
│   ├── schemas/
│   └── services/
├── .env
├── requirements.txt
├── README.md
└── seed_data.py
```

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a PostgreSQL database such as `finance_db`.
4. Create a `.env` file and add/update values.
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
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/finance_db
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

## Access Rules

- `viewer`: can read only their own transactions and dashboard data.
- `analyst`: can read all transactions and system-wide dashboards, but cannot create, update, or delete.
- `admin`: full access to users and transactions. Dashboard summary follows the requested spec and returns personal data, while analysts get system-wide data.

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
10. JWT tokens expire after 30 minutes.

## Manual Test Flow

1. Register or seed `admin`, `analyst`, and `viewer` users.
2. Login via `POST /api/auth/login` using form-data (`username`, `password`).
3. Create transactions as admin.
4. Verify role restrictions:
   - viewer create transaction -> `403`
   - analyst list all transactions -> `200`
   - admin delete transaction -> `204` and the row remains in PostgreSQL with `is_deleted=true`
5. Validate dashboard numbers and filters, confirming soft-deleted transactions no longer appear in transaction reads or dashboard totals.

## Notes

- Tables are auto-created on app startup through SQLAlchemy metadata.
- On startup, the app also ensures the `transactions.is_deleted` column exists for older databases and defaults existing rows to `false`.
- The API uses FastAPI docs at `/docs`.
