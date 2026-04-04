import { buildApiUrl } from "./config.js";
import { clearSession, getSession } from "./session.js";

function joinQuery(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    query.set(key, String(value));
  });
  const serialized = query.toString();
  return serialized ? `?${serialized}` : "";
}

export class ApiError extends Error {
  constructor(message, options = {}) {
    super(message);
    this.name = "ApiError";
    Object.assign(this, options);
  }
}

async function parseApiError(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  const retryAfterHeader = response.headers.get("Retry-After");
  const retryAfterSeconds =
    Number(payload?.detail?.retry_after_seconds ?? retryAfterHeader ?? 0) || null;

  const error = new ApiError(
    payload?.detail?.message ??
      payload?.detail?.error ??
      payload?.detail ??
      `Request failed with status ${response.status}`,
    {
      status: response.status,
      detail: payload?.detail ?? null,
      validationErrors: payload?.errors ?? [],
      retryAfterSeconds,
      headers: {
        limit: response.headers.get("X-RateLimit-Limit"),
        remaining: response.headers.get("X-RateLimit-Remaining"),
        reset: response.headers.get("X-RateLimit-Reset"),
      },
    },
  );

  if (response.status === 401) {
    clearSession();
    window.dispatchEvent(new CustomEvent("auth:expired"));
  }

  throw error;
}

async function request(path, options = {}) {
  const session = getSession();
  const headers = new Headers(options.headers ?? {});
  if (session?.token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${session.token}`);
  }
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  const response = await fetch(buildApiUrl(path), { ...options, headers });
  if (!response.ok) {
    return parseApiError(response);
  }

  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  login({ email, password }) {
    const body = new URLSearchParams();
    body.set("username", email);
    body.set("password", password);
    return request("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
  },
  register(payload) {
    return request("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  me() {
    return request("/users/me");
  },
  listUsers() {
    return request("/users");
  },
  updateUserRole(userId, role) {
    return request(`/users/${userId}/role`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
  },
  updateUserStatus(userId, isActive) {
    return request(`/users/${userId}/status`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: isActive }),
    });
  },
  listTransactions(params) {
    return request(`/transactions${joinQuery(params)}`);
  },
  getTransaction(transactionId) {
    return request(`/transactions/${transactionId}`);
  },
  createTransaction(payload) {
    return request("/transactions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  updateTransaction(transactionId, payload) {
    return request(`/transactions/${transactionId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  deleteTransaction(transactionId) {
    return request(`/transactions/${transactionId}`, { method: "DELETE" });
  },
  dashboardSummary() {
    return request("/dashboard/summary");
  },
  dashboardCategoryBreakdown() {
    return request("/dashboard/category-breakdown");
  },
  dashboardMonthlyTrends(year) {
    return request(`/dashboard/monthly-trends${joinQuery({ year })}`);
  },
  dashboardRecent(limit) {
    return request(`/dashboard/recent${joinQuery({ limit })}`);
  },
};
