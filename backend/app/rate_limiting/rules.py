"""Reusable rate limit rule definitions."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    """Describes a fixed-window rate limit."""

    name: str
    description: str
    max_requests: int
    window_seconds: int


# Public auth endpoints stay IP-based to slow down brute-force attempts and
# reduce spam signups without penalizing authenticated users sharing a device.
LOGIN_LIMIT = RateLimitRule(
    name="auth_login",
    description="5 login attempts per minute",
    max_requests=5,
    window_seconds=60,
)
REGISTER_LIMIT = RateLimitRule(
    name="auth_register",
    description="3 registration attempts per minute",
    max_requests=3,
    window_seconds=60,
)

# Read endpoints use more forgiving limits so normal browsing and pagination are
# comfortable, while still discouraging automated scraping.
READ_ME_LIMIT = RateLimitRule(
    name="users_me_read",
    description="60 profile reads per minute",
    max_requests=60,
    window_seconds=60,
)
LIST_TRANSACTIONS_LIMIT = RateLimitRule(
    name="transactions_list",
    description="60 transaction list requests per minute",
    max_requests=60,
    window_seconds=60,
)
READ_TRANSACTION_LIMIT = RateLimitRule(
    name="transactions_read",
    description="60 transaction detail requests per minute",
    max_requests=60,
    window_seconds=60,
)
LIST_USERS_LIMIT = RateLimitRule(
    name="users_list",
    description="30 user list requests per minute",
    max_requests=30,
    window_seconds=60,
)

# Dashboard queries can become aggregation-heavy, so they get stricter caps.
DASHBOARD_SUMMARY_LIMIT = RateLimitRule(
    name="dashboard_summary",
    description="30 dashboard summary requests per minute",
    max_requests=30,
    window_seconds=60,
)
DASHBOARD_CATEGORY_BREAKDOWN_LIMIT = RateLimitRule(
    name="dashboard_category_breakdown",
    description="30 dashboard category breakdown requests per minute",
    max_requests=30,
    window_seconds=60,
)
DASHBOARD_MONTHLY_TRENDS_LIMIT = RateLimitRule(
    name="dashboard_monthly_trends",
    description="30 dashboard monthly trend requests per minute",
    max_requests=30,
    window_seconds=60,
)
DASHBOARD_RECENT_LIMIT = RateLimitRule(
    name="dashboard_recent",
    description="30 dashboard recent activity requests per minute",
    max_requests=30,
    window_seconds=60,
)

# Writes are the most sensitive operations, especially admin actions.
CREATE_TRANSACTION_LIMIT = RateLimitRule(
    name="transactions_create",
    description="20 transaction creation requests per minute",
    max_requests=20,
    window_seconds=60,
)
UPDATE_TRANSACTION_LIMIT = RateLimitRule(
    name="transactions_update",
    description="20 transaction update requests per minute",
    max_requests=20,
    window_seconds=60,
)
DELETE_TRANSACTION_LIMIT = RateLimitRule(
    name="transactions_delete",
    description="10 transaction delete requests per minute",
    max_requests=10,
    window_seconds=60,
)
CHANGE_USER_ROLE_LIMIT = RateLimitRule(
    name="users_role_update",
    description="10 user role change requests per minute",
    max_requests=10,
    window_seconds=60,
)
CHANGE_USER_STATUS_LIMIT = RateLimitRule(
    name="users_status_update",
    description="10 user status change requests per minute",
    max_requests=10,
    window_seconds=60,
)

RATE_LIMIT_RULES = {
    "POST /api/auth/login": LOGIN_LIMIT,
    "POST /api/auth/register": REGISTER_LIMIT,
    "GET /api/users/me": READ_ME_LIMIT,
    "GET /api/users": LIST_USERS_LIMIT,
    "PUT /api/users/{user_id}/role": CHANGE_USER_ROLE_LIMIT,
    "PUT /api/users/{user_id}/status": CHANGE_USER_STATUS_LIMIT,
    "POST /api/transactions": CREATE_TRANSACTION_LIMIT,
    "GET /api/transactions": LIST_TRANSACTIONS_LIMIT,
    "GET /api/transactions/{transaction_id}": READ_TRANSACTION_LIMIT,
    "PUT /api/transactions/{transaction_id}": UPDATE_TRANSACTION_LIMIT,
    "DELETE /api/transactions/{transaction_id}": DELETE_TRANSACTION_LIMIT,
    "GET /api/dashboard/summary": DASHBOARD_SUMMARY_LIMIT,
    "GET /api/dashboard/category-breakdown": DASHBOARD_CATEGORY_BREAKDOWN_LIMIT,
    "GET /api/dashboard/monthly-trends": DASHBOARD_MONTHLY_TRENDS_LIMIT,
    "GET /api/dashboard/recent": DASHBOARD_RECENT_LIMIT,
}
