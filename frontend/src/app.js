import { api, ApiError } from "./api.js";
import { config } from "./config.js";
import { clearSession, getSession, isAuthenticated, setToken, setUser } from "./session.js";
import { currency, dateInputValue, escapeHtml, fieldErrorMap, shortDate, titleCase } from "./utils.js";

const app = document.querySelector("#app");

const state = {
  route: window.location.hash.replace(/^#/, "") || "/dashboard",
  authMode: "login",
  globalMessage: null,
  toasts: [],
  modal: {
    open: false,
    title: "",
    body: "",
    confirmLabel: "Confirm",
    tone: "danger",
    action: null,
    returnFocusSelector: null,
  },
  dashboard: {
    loading: false,
    year: "",
    recentLimit: 10,
    summary: null,
    breakdown: null,
    trends: [],
    recent: [],
  },
  transactions: {
    loading: false,
    page: 1,
    pageSize: 10,
    total: 0,
    filters: { type: "", category: "", start_date: "", end_date: "" },
    items: [],
    formMode: "create",
    selectedId: null,
    formErrors: {},
    formMessage: null,
    saving: false,
  },
  users: {
    loading: false,
    items: [],
    pendingRoles: {},
    rowMessages: {},
  },
};

const navByRole = {
  viewer: [
    { path: "/dashboard", label: "Overview" },
    { path: "/transactions", label: "My Transactions" },
  ],
  analyst: [
    { path: "/dashboard", label: "Global Dashboard" },
    { path: "/transactions", label: "Transactions" },
  ],
  admin: [
    { path: "/dashboard", label: "Overview" },
    { path: "/transactions", label: "Transactions" },
    { path: "/users", label: "User Admin" },
  ],
};

window.addEventListener("hashchange", () => {
  state.route = window.location.hash.replace(/^#/, "") || "/dashboard";
  render();
  hydrateRoute();
});

window.addEventListener("auth:expired", () => {
  toast("Session expired. Please log in again.", "warning");
  render();
});

function toast(message, tone = "info") {
  const id = crypto.randomUUID();
  state.toasts.push({ id, message, tone });
  renderToasts();
  window.setTimeout(() => {
    state.toasts = state.toasts.filter((item) => item.id !== id);
    renderToasts();
  }, 4200);
}

function setRoute(path) {
  if (window.location.hash !== `#${path}`) {
    window.location.hash = path;
    return;
  }
  state.route = path;
  render();
  hydrateRoute();
}

function openModal(options) {
  state.modal = {
    open: true,
    title: options.title,
    body: options.body,
    confirmLabel: options.confirmLabel ?? "Confirm",
    tone: options.tone ?? "danger",
    action: options.action ?? null,
    returnFocusSelector: options.returnFocusSelector ?? null,
  };
  render();
  requestAnimationFrame(() => {
    document.querySelector("[data-modal-confirm]")?.focus();
  });
}

function closeModal() {
  const returnFocusSelector = state.modal.returnFocusSelector;
  state.modal = {
    open: false,
    title: "",
    body: "",
    confirmLabel: "Confirm",
    tone: "danger",
    action: null,
    returnFocusSelector: null,
  };
  render();
  if (returnFocusSelector) {
    requestAnimationFrame(() => {
      document.querySelector(returnFocusSelector)?.focus();
    });
  }
}

function getCurrentUser() {
  return getSession().user;
}

function isAdmin() {
  return getCurrentUser()?.role === "admin";
}

function isAnalyst() {
  return getCurrentUser()?.role === "analyst";
}

function ensureRouteAllowed() {
  const user = getCurrentUser();
  if (!user) return;
  if (state.route === "/users" && user.role !== "admin") {
    setRoute("/dashboard");
  }
}

async function bootstrap() {
  render();
  if (isAuthenticated()) {
    await refreshCurrentUser();
    await hydrateRoute();
  }
  render();
}

async function refreshCurrentUser() {
  try {
    const user = await api.me();
    setUser(user);
  } catch (error) {
    handleApiError(error, { form: false });
  }
}

function handleApiError(error, options = {}) {
  if (!(error instanceof ApiError)) {
    toast("Unexpected error. Please try again.", "error");
    return { formErrors: {}, message: "Unexpected error." };
  }

  if (error.status === 401) {
    clearSession();
    render();
    return { formErrors: {}, message: "Your session has ended." };
  }

  if (error.status === 403) {
    toast("You are signed in, but this action is not allowed for your role.", "warning");
  } else if (error.status === 429) {
    const retryCopy = error.retryAfterSeconds
      ? `Too many requests. Try again in ${error.retryAfterSeconds} seconds.`
      : "Too many requests. Please pause and try again shortly.";
    toast(retryCopy, "warning");
  } else if (!options.form) {
    toast(error.message || "Request failed.", "error");
  }

  return {
    formErrors: fieldErrorMap(error),
    message: error.message || "Request failed.",
  };
}

async function hydrateRoute() {
  if (!isAuthenticated()) return;
  ensureRouteAllowed();
  if (state.route === "/dashboard") await loadDashboard();
  if (state.route === "/transactions") await loadTransactions();
  if (state.route === "/users" && isAdmin()) await loadUsers();
}

async function loadDashboard() {
  state.dashboard.loading = true;
  render();
  try {
    const [summary, breakdown, trends, recent] = await Promise.all([
      api.dashboardSummary(),
      api.dashboardCategoryBreakdown(),
      api.dashboardMonthlyTrends(state.dashboard.year || undefined),
      api.dashboardRecent(state.dashboard.recentLimit),
    ]);
    state.dashboard.summary = summary;
    state.dashboard.breakdown = breakdown;
    state.dashboard.trends = trends;
    state.dashboard.recent = recent;
  } catch (error) {
    handleApiError(error);
  } finally {
    state.dashboard.loading = false;
    render();
  }
}

async function loadTransactions() {
  state.transactions.loading = true;
  render();
  try {
    const result = await api.listTransactions({
      ...state.transactions.filters,
      page: state.transactions.page,
      page_size: state.transactions.pageSize,
    });
    state.transactions.items = result.items;
    state.transactions.total = result.total;
    state.transactions.page = result.page;
    state.transactions.pageSize = result.page_size;
  } catch (error) {
    handleApiError(error);
  } finally {
    state.transactions.loading = false;
    render();
  }
}

async function loadUsers() {
  state.users.loading = true;
  render();
  try {
    state.users.items = await api.listUsers();
  } catch (error) {
    handleApiError(error);
  } finally {
    state.users.loading = false;
    render();
  }
}

function render() {
  app.innerHTML = `${isAuthenticated() && getCurrentUser() ? renderShell() : renderAuth()}${renderModal()}`;
  bindEvents();
  renderToasts();
}

function renderToasts() {
  let stack = document.querySelector(".toast-stack");
  if (!stack) {
    stack = document.createElement("div");
    stack.className = "toast-stack";
    document.body.appendChild(stack);
  }
  stack.innerHTML = state.toasts
    .map((item) => `<div class="toast ${escapeHtml(item.tone)}">${escapeHtml(item.message)}</div>`)
    .join("");
}

function renderAuth() {
  const authMode = state.authMode;
  const message = state.globalMessage;
  return `
    <div class="auth-shell">
      <div class="auth-layout auth-layout-single">
        <section class="auth-panel">
          <div class="auth-tabs">
            <button class="auth-tab ${authMode === "login" ? "active" : ""}" data-auth-tab="login">Login</button>
            <button class="auth-tab ${authMode === "register" ? "active" : ""}" data-auth-tab="register">Register</button>
          </div>
          <h2>${authMode === "login" ? "Welcome back" : "Create your account"}</h2>
          ${
            message
              ? `<div class="banner ${escapeHtml(message.tone ?? "info")}">${escapeHtml(message.text)}</div>`
              : ""
          }
          ${authMode === "login" ? renderLoginForm() : renderRegisterForm()}
        </section>
      </div>
    </div>
  `;
}

function renderModal() {
  if (!state.modal.open) return "";
  return `
    <div class="modal-backdrop" data-action="close-modal">
      <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="modal-title" aria-describedby="modal-body">
        <h3 id="modal-title" class="section-title">${escapeHtml(state.modal.title)}</h3>
        <p id="modal-body" class="hero-copy">${escapeHtml(state.modal.body)}</p>
        <div class="inline-actions">
          <button class="secondary-button" type="button" data-action="cancel-modal">Cancel</button>
          <button class="${state.modal.tone === "danger" ? "danger-button" : "primary-button"}" type="button" data-modal-confirm>${escapeHtml(state.modal.confirmLabel)}</button>
        </div>
      </div>
    </div>
  `;
}

function passwordStrengthMeta(password) {
  const checks = [
    password.length >= 8,
    /[A-Z]/.test(password),
    /[a-z]/.test(password),
    /\d/.test(password),
    /[^A-Za-z0-9]/.test(password),
  ];
  const score = checks.filter(Boolean).length;
  if (score <= 2) return { label: "Low", className: "low", width: 28 };
  if (score <= 4) return { label: "Medium", className: "medium", width: 64 };
  return { label: "Strong", className: "strong", width: 100 };
}

function renderLoginForm() {
  return `
    <form id="login-form" class="form-grid">
      <div class="field span-12">
        <label for="login-email">Email</label>
        <input id="login-email" name="email" type="email" autocomplete="username" required />
        <div class="field-error" data-error-for="email"></div>
      </div>
      <div class="field span-12">
        <label for="login-password">Password</label>
        <div class="input-with-action">
          <input id="login-password" name="password" type="password" autocomplete="current-password" required />
          <button class="field-action" type="button" data-action="toggle-password" data-target="login-password">Show</button>
        </div>
        <div class="field-error" data-error-for="password"></div>
      </div>
      <div class="field span-12">
        <button class="primary-button" type="submit">Sign in</button>
      </div>
    </form>
  `;
}

function renderRegisterForm() {
  const strength = passwordStrengthMeta("");
  return `
    <form id="register-form" class="form-grid">
      <div class="field span-6">
        <label for="register-email">Email</label>
        <input id="register-email" name="email" type="email" autocomplete="email" required />
        <div class="field-error" data-error-for="email"></div>
      </div>
      <div class="field span-6">
        <label for="register-full-name">Full name</label>
        <input id="register-full-name" name="full_name" type="text" maxlength="255" autocomplete="name" />
        <div class="field-error" data-error-for="full_name"></div>
      </div>
      <div class="field span-6">
        <label for="register-password">Password</label>
        <div class="input-with-action">
          <input id="register-password" name="password" type="password" minlength="8" maxlength="128" autocomplete="new-password" required />
          <button class="field-action" type="button" data-action="toggle-password" data-target="register-password">Show</button>
        </div>
        <div class="strength-meter" aria-live="polite">
          <div class="strength-track"><span class="strength-fill ${strength.className}" style="width:${strength.width}%"></span></div>
          <span class="strength-label" data-password-strength-label>${strength.label}</span>
        </div>
        <div class="field-hint">Use at least 8 characters with 1 letter and 1 number.</div>
        <div class="field-error" data-error-for="password"></div>
      </div>
      <div class="field span-6">
        <label for="register-role">Role</label>
        <select id="register-role" name="role">
          <option value="viewer">Viewer</option>
          <option value="analyst">Analyst</option>
          <option value="admin">Admin</option>
        </select>
        <div class="field-error" data-error-for="role"></div>
      </div>
      <div class="field span-12">
        <button class="primary-button" type="submit">Create account</button>
      </div>
    </form>
  `;
}

function renderShell() {
  const user = getCurrentUser();
  const nav = navByRole[user.role] ?? navByRole.viewer;
  return `
    <div class="shell">
      <aside class="sidebar">
        <div class="brand">
          <div class="brand-mark">Z</div>
          <div>
            <h1>Zorvyn Finance</h1>
            <p class="muted">FastAPI-connected operations console</p>
          </div>
        </div>
        <nav class="nav" aria-label="Primary">
          ${nav
            .map(
              (item) => `
                <a href="#${item.path}" class="${state.route === item.path ? "active" : ""}" ${state.route === item.path ? 'aria-current="page"' : ""}>
                  ${escapeHtml(item.label)}
                </a>
              `,
            )
            .join("")}
        </nav>
        <div class="sidebar-footer">
          <div class="user-chip">
            <div><strong>${escapeHtml(user.full_name || user.email)}</strong></div>
            <div class="muted">${escapeHtml(user.email)}</div>
            <div style="margin-top:10px"><span class="role-badge">${escapeHtml(user.role)}</span></div>
          </div>
          <button class="secondary-button" data-action="logout">Sign out</button>
        </div>
      </aside>
      <main class="main" id="main-content" tabindex="-1">${renderPage()}</main>
    </div>
  `;
}

function renderPage() {
  if (state.route === "/transactions") return renderTransactionsPage();
  if (state.route === "/users" && isAdmin()) return renderUsersPage();
  return renderDashboardPage();
}

function renderDashboardPage() {
  const { loading, summary, breakdown, trends, recent, year, recentLimit } = state.dashboard;
  const scopeCopy = isAnalyst()
    ? "System-wide metrics are shown because your analyst role can view active users across the platform."
    : "These dashboard metrics are scoped to your own transactions, matching backend behavior for viewer and admin roles.";

  return `
    <section class="topbar">
      <div>
        <div class="muted">Dashboard</div>
        <h2 class="page-title" tabindex="-1">${isAnalyst() ? "Global Finance Pulse" : "Your Finance Snapshot"}</h2>
        <div class="hero-copy">${scopeCopy}</div>
      </div>
      <div class="panel">
        <div class="field">
          <label for="dashboard-year">Trend year</label>
          <input id="dashboard-year" type="number" min="2000" max="2100" value="${escapeHtml(year)}" placeholder="All years" />
        </div>
        <div class="field" style="margin-top:12px">
          <label for="dashboard-limit">Recent items</label>
          <select id="dashboard-limit">
            ${[5, 10, 20, 30, 50]
              .map((value) => `<option value="${value}" ${value === recentLimit ? "selected" : ""}>${value}</option>`)
              .join("")}
          </select>
        </div>
        <div class="inline-actions" style="margin-top:14px">
          <button class="primary-button" data-action="refresh-dashboard">Refresh</button>
        </div>
      </div>
    </section>
    ${
      loading
        ? renderDashboardSkeleton()
        : `
          <div class="dashboard-grid">
            <div class="stats-grid">
              ${renderStatCard("Total Income", summary ? currency(summary.total_income) : "-", "Revenue captured across the current scope.")}
              ${renderStatCard("Total Expense", summary ? currency(summary.total_expense) : "-", "Outgoing spend across the current scope.")}
              ${renderStatCard("Net Balance", summary ? currency(summary.net_balance) : "-", "Income minus expense.")}
              ${renderStatCard("Transactions", summary ? String(summary.transaction_count) : "-", `Period: ${summary?.period ?? "all_time"}`)}
            </div>
            <section class="panel span-7" aria-labelledby="trends-title">
              <div class="section-header">
                <h3 class="section-title" id="trends-title">Monthly Trends</h3>
                <div class="muted">${trends.length ? `${trends.length} months` : "No data"}</div>
              </div>
              ${renderTrendsChart(trends)}
            </section>
            <section class="panel span-5" aria-labelledby="breakdown-title">
              <div class="section-header">
                <h3 class="section-title" id="breakdown-title">Category Breakdown</h3>
                <div class="muted">Income vs expense</div>
              </div>
              ${renderBreakdown(breakdown)}
            </section>
            <section class="panel span-12" aria-labelledby="recent-title">
              <div class="section-header">
                <h3 class="section-title" id="recent-title">Recent Activity</h3>
                <div class="muted">Latest ${recentLimit} transactions</div>
              </div>
              ${renderRecent(recent)}
            </section>
          </div>
        `
    }
  `;
}

function renderDashboardSkeleton() {
  return `
    <div class="dashboard-grid">
      <div class="stats-grid">
        <div class="skeleton-card"></div>
        <div class="skeleton-card"></div>
        <div class="skeleton-card"></div>
        <div class="skeleton-card"></div>
      </div>
      <div class="panel span-7"><div class="skeleton-block large"></div></div>
      <div class="panel span-5"><div class="skeleton-block large"></div></div>
      <div class="panel span-12"><div class="skeleton-block medium"></div></div>
    </div>
  `;
}

function renderStatCard(label, value, note) {
  return `
    <div class="stat-card">
      <div class="stat-label">${escapeHtml(label)}</div>
      <div class="stat-value">${escapeHtml(value)}</div>
      <div class="muted">${escapeHtml(note)}</div>
    </div>
  `;
}

function renderTrendsChart(trends) {
  if (!trends?.length) {
    return `<div class="empty-state"><p>No monthly trend data is available for the selected range.</p></div>`;
  }
  const maxValue = Math.max(
    ...trends.flatMap((item) => [Number(item.income ?? 0), Number(item.expense ?? 0)]),
    1,
  );
  return `
    <div class="chart-legend">
      <span class="legend-dot income"></span><span class="muted">Income</span>
      <span class="legend-dot expense"></span><span class="muted">Expense</span>
    </div>
    <div class="chart-bars" aria-hidden="true">
      ${trends
        .map((item) => {
          const incomeHeight = Math.max((Number(item.income) / maxValue) * 180, 6);
          const expenseHeight = Math.max((Number(item.expense) / maxValue) * 180, 6);
          return `
            <div class="chart-column" title="Income ${currency(item.income)} | Expense ${currency(item.expense)} | Net ${currency(item.net)}">
              <div class="chart-stack">
                <div class="chart-bar income" style="height:${incomeHeight}px"></div>
                <div class="chart-bar expense" style="height:${expenseHeight}px"></div>
              </div>
              <div class="muted">${escapeHtml(item.month.slice(5))}</div>
            </div>
          `;
        })
        .join("")}
    </div>
    <table class="sr-only">
      <caption>Monthly trend summary</caption>
      <thead><tr><th>Month</th><th>Income</th><th>Expense</th><th>Net</th></tr></thead>
      <tbody>
        ${trends
          .map(
            (item) => `<tr><td>${escapeHtml(item.month)}</td><td>${escapeHtml(currency(item.income))}</td><td>${escapeHtml(currency(item.expense))}</td><td>${escapeHtml(currency(item.net))}</td></tr>`,
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function renderBreakdown(breakdown) {
  const renderBucketList = (title, items, emptyCopy) => `
    <div>
      <div class="summary-line" style="margin-bottom:12px">
        <strong>${escapeHtml(title)}</strong>
        <span class="counter-pill">${items?.length ?? 0} categories</span>
      </div>
      ${
        items?.length
          ? `<div class="info-list">${items
              .map(
                (item) => `
                  <div class="bucket">
                    <div class="summary-line">
                      <strong>${escapeHtml(item.category)}</strong>
                      <span class="counter-pill">${item.count} txns</span>
                    </div>
                    <div class="muted">${currency(item.total)}</div>
                  </div>
                `,
              )
              .join("")}</div>`
          : `<div class="empty-state"><p>${escapeHtml(emptyCopy)}</p></div>`
      }
    </div>
  `;

  return `
    <div class="breakdown-columns">
      ${renderBucketList("Income", breakdown?.income, "No income categories available yet.")}
      ${renderBucketList("Expense", breakdown?.expense, "No expense categories available yet.")}
    </div>
  `;
}

function renderRecent(items) {
  if (!items?.length) {
    return `
      <div class="empty-state">
        <p>No recent transactions were returned.</p>
        ${isAdmin() ? `<button class="secondary-button" data-action="new-transaction">Add a transaction</button>` : ""}
      </div>
    `;
  }
  return `
    <div class="recent-list">
      ${items
        .map(
          (item) => `
            <div class="recent-item">
              <div class="summary-line">
                <strong>${escapeHtml(item.category)}</strong>
                <span class="type-pill ${escapeHtml(item.type)}">${escapeHtml(item.type)}</span>
              </div>
              <div class="summary-line" style="margin-top:10px">
                <span>${shortDate(item.date)}</span>
                <strong>${currency(item.amount)}</strong>
              </div>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderTransactionsPage() {
  const user = getCurrentUser();
  const { loading, items, total, page, pageSize, filters, formMode, selectedId, formErrors, formMessage, saving } =
    state.transactions;
  const totalPages = Math.max(Math.ceil(total / pageSize), 1);

  return `
    <section class="topbar">
      <div>
        <div class="muted">Transactions</div>
        <h2 class="page-title" tabindex="-1">${user.role === "viewer" ? "Your Transaction Ledger" : "Transaction Control Center"}</h2>
        <div class="hero-copy">
          Filter by type, category, and date range. ${isAdmin() ? "Admins can create, edit, and soft-delete transactions." : "This view respects the backend access rules for your role."}
        </div>
      </div>
      ${isAdmin() ? `<button class="primary-button" data-action="new-transaction">New transaction</button>` : ""}
    </section>
    <div class="page-grid">
      <section class="panel" aria-labelledby="transaction-filters-title">
        <div class="section-header">
          <h3 class="section-title" id="transaction-filters-title">Filters</h3>
          <button class="ghost-button" data-action="reset-transaction-filters">Reset</button>
        </div>
        <form id="transaction-filters" class="filter-grid">
          <div class="field span-3">
            <label for="filter-type">Type</label>
            <select id="filter-type" name="type">
              <option value="">All</option>
              <option value="income" ${filters.type === "income" ? "selected" : ""}>Income</option>
              <option value="expense" ${filters.type === "expense" ? "selected" : ""}>Expense</option>
            </select>
          </div>
          <div class="field span-3">
            <label for="filter-category">Category</label>
            <input id="filter-category" name="category" type="text" value="${escapeHtml(filters.category)}" placeholder="substring match" />
          </div>
          <div class="field span-3">
            <label for="filter-start-date">Start date</label>
            <input id="filter-start-date" name="start_date" type="date" value="${escapeHtml(filters.start_date)}" />
          </div>
          <div class="field span-3">
            <label for="filter-end-date">End date</label>
            <input id="filter-end-date" name="end_date" type="date" value="${escapeHtml(filters.end_date)}" />
          </div>
          <div class="field span-12">
            <div class="inline-actions">
              <button class="primary-button" type="submit">Apply filters</button>
            </div>
          </div>
        </form>
      </section>
      ${isAdmin() ? renderTransactionFormPanel(formMode, selectedId, formErrors, formMessage, saving) : ""}
      <section class="panel" aria-labelledby="transaction-results-title">
        <div class="section-header">
          <h3 class="section-title" id="transaction-results-title">Results</h3>
          <div class="muted">${total} total matching transactions</div>
        </div>
        ${
          loading
            ? renderTableSkeleton(8, isAdmin() ? 7 : 6)
            : items.length
              ? renderTransactionTable(items)
              : `
                <div class="empty-state">
                  <p>No transactions match the current filters.</p>
                  ${isAdmin() ? `<button class="secondary-button" data-action="new-transaction">Add a transaction</button>` : ""}
                </div>
              `
        }
        <div class="pagination">
          <div class="muted">Page ${page} of ${totalPages} | ${pageSize} per page</div>
          <div class="inline-actions">
            <button class="secondary-button" data-action="prev-page" ${page <= 1 ? "disabled" : ""}>Previous</button>
            <button class="secondary-button" data-action="next-page" ${page >= totalPages ? "disabled" : ""}>Next</button>
          </div>
        </div>
      </section>
    </div>
  `;
}

function renderTableSkeleton(rows, columns) {
  return `
    <div class="table-shell">
      <div class="table-skeleton-grid" style="--columns:${columns}">
        ${Array.from({ length: rows * columns }, () => '<span class="table-skeleton-cell"></span>').join("")}
      </div>
    </div>
  `;
}

function renderTransactionTable(items) {
  return `
    <div class="table-shell">
      <table class="data-table">
        <thead>
          <tr>
            <th>Category</th>
            <th>Type</th>
            <th>Owner</th>
            <th>Date</th>
            <th class="numeric">Amount</th>
            <th>Description</th>
            ${isAdmin() ? "<th>Actions</th>" : ""}
          </tr>
        </thead>
        <tbody>
          ${items
            .map(
              (item) => `
                <tr>
                  <td><strong>${escapeHtml(item.category)}</strong></td>
                  <td><span class="type-pill ${escapeHtml(item.type)}">${escapeHtml(item.type)}</span></td>
                  <td>#${item.user_id}</td>
                  <td>${shortDate(item.date)}</td>
                  <td class="numeric tabular">${currency(item.amount)}</td>
                  <td class="truncate-cell">${escapeHtml(item.description || "-")}</td>
                  ${
                    isAdmin()
                      ? `
                        <td>
                          <div class="inline-actions">
                            <button class="pill-button" data-action="edit-transaction" data-id="${item.id}" id="edit-transaction-${item.id}">Edit</button>
                            <button class="pill-button" data-action="delete-transaction" data-id="${item.id}" id="delete-transaction-${item.id}">Delete</button>
                          </div>
                        </td>
                      `
                      : ""
                  }
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderTransactionFormPanel(formMode, selectedId, formErrors, formMessage, saving) {
  const selected =
    state.transactions.items.find((item) => item.id === selectedId) ?? {
      amount: "",
      type: "income",
      category: "",
      date: config.today,
      description: "",
      user_id: "",
    };

  return `
    <section class="panel">
      <div class="section-header">
        <h3 class="section-title">${formMode === "edit" ? `Edit #${selectedId}` : "Create Transaction"}</h3>
        <button class="ghost-button" data-action="clear-transaction-form">Clear</button>
      </div>
      ${formMessage ? `<div class="inline-message ${escapeHtml(formMessage.tone)}">${escapeHtml(formMessage.text)}</div>` : ""}
      <form id="transaction-form" class="form-grid">
        <div class="field span-4">
          <label for="transaction-amount">Amount</label>
          <input id="transaction-amount" name="amount" type="number" min="0.01" step="0.01" value="${escapeHtml(selected.amount)}" required />
          <div class="field-error" data-error-for="amount">${escapeHtml(formErrors.amount ?? "")}</div>
        </div>
        <div class="field span-4">
          <label for="transaction-type">Type</label>
          <select id="transaction-type" name="type">
            <option value="income" ${selected.type === "income" ? "selected" : ""}>Income</option>
            <option value="expense" ${selected.type === "expense" ? "selected" : ""}>Expense</option>
          </select>
          <div class="field-error" data-error-for="type">${escapeHtml(formErrors.type ?? "")}</div>
        </div>
        <div class="field span-4">
          <label for="transaction-date">Date</label>
          <input id="transaction-date" name="date" type="date" max="${config.today}" value="${escapeHtml(dateInputValue(selected.date) || config.today)}" required />
          <div class="field-error" data-error-for="date">${escapeHtml(formErrors.date ?? "")}</div>
        </div>
        <div class="field span-8">
          <label for="transaction-category">Category</label>
          <input id="transaction-category" name="category" type="text" maxlength="100" value="${escapeHtml(selected.category ?? "")}" required />
          <div class="field-error" data-error-for="category">${escapeHtml(formErrors.category ?? "")}</div>
        </div>
        <div class="field span-4">
          ${
            formMode === "edit"
              ? `
                <label for="transaction-user-id">Current owner</label>
                <input id="transaction-user-id" type="text" value="User #${escapeHtml(selected.user_id ?? "")}" disabled />
                <div class="field-hint">Owner changes are not part of the update endpoint.</div>
              `
              : `
                <label for="transaction-user-id">Owner user ID</label>
                <input id="transaction-user-id" name="user_id" type="number" min="1" step="1" value="${escapeHtml(selected.user_id ?? "")}" placeholder="defaults to me" />
                <div class="field-hint">Optional on create. Leave blank to use your admin account.</div>
                <div class="field-error" data-error-for="user_id">${escapeHtml(formErrors.user_id ?? "")}</div>
              `
          }
        </div>
        <div class="field span-12">
          <label for="transaction-description">Description</label>
          <textarea id="transaction-description" name="description" maxlength="500">${escapeHtml(selected.description ?? "")}</textarea>
          <div class="field-error" data-error-for="description">${escapeHtml(formErrors.description ?? "")}</div>
        </div>
        <div class="field span-12">
          <div class="inline-actions">
            <button class="primary-button" type="submit" ${saving ? "disabled" : ""}>${formMode === "edit" ? "Save changes" : "Create transaction"}</button>
            ${formMode === "edit" ? `<button class="danger-button" type="button" data-action="delete-current-transaction">Delete</button>` : ""}
          </div>
        </div>
      </form>
    </section>
  `;
}

function renderTransactionItem(item) {
  const adminActions = isAdmin()
    ? `
      <div class="inline-actions">
        <button class="pill-button" data-action="edit-transaction" data-id="${item.id}">Edit</button>
        <button class="pill-button" data-action="delete-transaction" data-id="${item.id}">Delete</button>
      </div>
    `
    : "";

  return `
    <div class="transaction-item">
      <div class="summary-line">
        <div>
          <strong>${escapeHtml(item.category)}</strong>
          <div class="muted">Owner #${item.user_id} | ${shortDate(item.date)}</div>
        </div>
        <div style="text-align:right">
          <div><strong>${currency(item.amount)}</strong></div>
          <div><span class="type-pill ${escapeHtml(item.type)}">${escapeHtml(item.type)}</span></div>
        </div>
      </div>
      <div class="summary-line" style="margin-top:12px">
        <div class="helper-copy">${escapeHtml(item.description || "No description")}</div>
        ${adminActions}
      </div>
    </div>
  `;
}

function renderUsersPage() {
  const currentUser = getCurrentUser();
  return `
    <section class="topbar">
      <div>
        <div class="muted">Administration</div>
        <h2 class="page-title" tabindex="-1">User Access Console</h2>
        <div class="hero-copy">
          Manage roles and active status for registered users. The backend will reject self-deactivation, and the UI also blocks it before submit.
        </div>
      </div>
      <button class="secondary-button" data-action="refresh-users">Refresh users</button>
    </section>
    <section class="panel" aria-labelledby="users-title">
      <div class="section-header">
        <h3 class="section-title" id="users-title">Users</h3>
        <div class="muted">${state.users.items.length} accounts</div>
      </div>
      ${
        state.users.loading
          ? renderTableSkeleton(8, 6)
          : state.users.items.length
            ? renderUserTable(state.users.items, currentUser)
            : `<div class="empty-state"><p>No users were returned by the API.</p></div>`
      }
    </section>
  `;
}

function renderUserTable(items, currentUser) {
  return `
    <div class="table-shell">
      <table class="data-table">
        <thead>
          <tr>
            <th>User</th>
            <th>Email</th>
            <th>Role</th>
            <th>Status</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${items.map((user) => renderUserRow(user, currentUser)).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderUserRow(user, currentUser) {
  const disableDeactivate = user.id === currentUser.id;
  const pendingRole = state.users.pendingRoles[user.id] ?? user.role;
  const rowMessage = state.users.rowMessages[user.id];
  return `
    <tr>
      <td>
        <strong>${escapeHtml(user.full_name || "Unnamed user")}</strong>
        <div class="muted">ID ${user.id}</div>
      </td>
      <td>${escapeHtml(user.email)}</td>
      <td>
        <select id="role-${user.id}" data-action="change-user-role" data-id="${user.id}">
          ${["viewer", "analyst", "admin"]
            .map((role) => `<option value="${role}" ${pendingRole === role ? "selected" : ""}>${titleCase(role)}</option>`)
            .join("")}
        </select>
      </td>
      <td><span class="status-pill ${user.is_active ? "active" : "inactive"}">${user.is_active ? "active" : "inactive"}</span></td>
      <td>${shortDate(user.created_at)}</td>
      <td>
        <div class="inline-actions">
          ${
            pendingRole !== user.role
              ? `<button class="pill-button" data-action="save-user-role" data-id="${user.id}">Save</button>`
              : ""
          }
          ${
            pendingRole !== user.role
              ? `<button class="ghost-button" data-action="reset-user-role" data-id="${user.id}">Cancel</button>`
              : ""
          }
          <button
            class="${user.is_active ? "danger-button" : "secondary-button"}"
            data-action="toggle-user-status"
            data-id="${user.id}"
            data-active="${user.is_active}"
            ${disableDeactivate ? "disabled" : ""}
          >
            ${user.is_active ? "Deactivate" : "Activate"}
          </button>
        </div>
        ${
          rowMessage
            ? `<div class="table-row-message ${escapeHtml(rowMessage.tone)}">${escapeHtml(rowMessage.text)}</div>`
            : disableDeactivate
              ? `<div class="field-hint">You cannot deactivate your own account.</div>`
              : ""
        }
      </td>
    </tr>
  `;
}

function bindEvents() {
  document.querySelectorAll("[data-auth-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      state.authMode = button.dataset.authTab;
      state.globalMessage = null;
      render();
    });
  });

  document.querySelector("[data-action='logout']")?.addEventListener("click", () => {
    clearSession();
    state.globalMessage = { tone: "info", text: "Signed out successfully." };
    render();
  });

  document.querySelector("#login-form")?.addEventListener("submit", onLoginSubmit);
  document.querySelector("#register-form")?.addEventListener("submit", onRegisterSubmit);
  document.querySelector("#transaction-filters")?.addEventListener("submit", onTransactionFilterSubmit);
  document.querySelector("#transaction-form")?.addEventListener("submit", onTransactionSubmit);
  document.querySelector("#dashboard-year")?.addEventListener("change", (event) => {
    state.dashboard.year = event.target.value;
  });
  document.querySelector("#dashboard-limit")?.addEventListener("change", (event) => {
    state.dashboard.recentLimit = Number(event.target.value);
  });
  document.querySelector("[data-action='refresh-dashboard']")?.addEventListener("click", loadDashboard);
  document.querySelector("[data-action='reset-transaction-filters']")?.addEventListener("click", resetTransactionFilters);
  document.querySelector("[data-action='new-transaction']")?.addEventListener("click", () => {
    state.transactions.formMode = "create";
    state.transactions.selectedId = null;
    state.transactions.formErrors = {};
    state.transactions.formMessage = null;
    render();
  });
  document.querySelector("[data-action='clear-transaction-form']")?.addEventListener("click", () => {
    state.transactions.formMode = "create";
    state.transactions.selectedId = null;
    state.transactions.formErrors = {};
    state.transactions.formMessage = null;
    render();
  });
  document.querySelector("[data-action='prev-page']")?.addEventListener("click", () => {
    state.transactions.page = Math.max(1, state.transactions.page - 1);
    loadTransactions();
  });
  document.querySelector("[data-action='next-page']")?.addEventListener("click", () => {
    state.transactions.page += 1;
    loadTransactions();
  });
  document.querySelector("[data-action='refresh-users']")?.addEventListener("click", loadUsers);
  document.querySelector("[data-action='delete-current-transaction']")?.addEventListener("click", async () => {
    if (!state.transactions.selectedId) return;
    await deleteTransaction(state.transactions.selectedId, `[data-action='delete-current-transaction']`);
  });

  document.querySelectorAll("[data-action='edit-transaction']").forEach((button) => {
    button.addEventListener("click", async () => {
      await startEditTransaction(Number(button.dataset.id));
    });
  });

  document.querySelectorAll("[data-action='delete-transaction']").forEach((button) => {
    button.addEventListener("click", async () => {
      await deleteTransaction(Number(button.dataset.id), `#delete-transaction-${button.dataset.id}`);
    });
  });

  document.querySelectorAll("[data-action='change-user-role']").forEach((select) => {
    select.addEventListener("change", () => {
      const userId = Number(select.dataset.id);
      state.users.pendingRoles[userId] = select.value;
      state.users.rowMessages[userId] = null;
      render();
    });
  });

  document.querySelectorAll("[data-action='save-user-role']").forEach((button) => {
    button.addEventListener("click", async () => {
      await changeUserRole(Number(button.dataset.id), state.users.pendingRoles[Number(button.dataset.id)]);
    });
  });

  document.querySelectorAll("[data-action='reset-user-role']").forEach((button) => {
    button.addEventListener("click", () => {
      const userId = Number(button.dataset.id);
      delete state.users.pendingRoles[userId];
      state.users.rowMessages[userId] = null;
      render();
    });
  });

  document.querySelectorAll("[data-action='toggle-user-status']").forEach((button) => {
    button.addEventListener("click", async () => {
      await toggleUserStatus(Number(button.dataset.id), button.dataset.active === "true");
    });
  });

  document.querySelectorAll("[data-action='toggle-password']").forEach((button) => {
    button.addEventListener("click", () => {
      const input = document.getElementById(button.dataset.target);
      if (!input) return;
      const nextType = input.type === "password" ? "text" : "password";
      input.type = nextType;
      button.textContent = nextType === "password" ? "Show" : "Hide";
    });
  });

  document.querySelector("#register-password")?.addEventListener("input", (event) => {
    updatePasswordStrength(event.target.value);
  });

  document.querySelector("[data-modal-confirm]")?.addEventListener("click", async () => {
    const action = state.modal.action;
    if (!action) return closeModal();
    await action();
    closeModal();
  });

  document.querySelector("[data-action='cancel-modal']")?.addEventListener("click", closeModal);
  document.querySelector(".modal-backdrop")?.addEventListener("click", (event) => {
    if (event.target.classList.contains("modal-backdrop")) closeModal();
  });

  requestAnimationFrame(() => {
    document.querySelector(".page-title")?.focus();
  });
}

async function onLoginSubmit(event) {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  clearFieldErrors(event.currentTarget);

  try {
    const token = await api.login({ email, password });
    setToken(token.access_token);
    const user = await api.me();
    setUser(user);
    state.globalMessage = null;
    setRoute("/dashboard");
    await hydrateRoute();
  } catch (error) {
    const { formErrors, message } = handleApiError(error, { form: true });
    applyFieldErrors(event.currentTarget, formErrors);
    state.globalMessage = { tone: "error", text: message };
    render();
  }
}

async function onRegisterSubmit(event) {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const payload = {
    email: String(formData.get("email") ?? "").trim(),
    password: String(formData.get("password") ?? ""),
    full_name: String(formData.get("full_name") ?? "").trim() || null,
    role: String(formData.get("role") ?? "viewer"),
  };

  const localErrors = {};
  if (!payload.password.match(/^(?=.*[A-Za-z])(?=.*\d).{8,128}$/)) {
    localErrors.password = "Password must be 8-128 chars with at least 1 letter and 1 number.";
  }
  clearFieldErrors(event.currentTarget);
  if (Object.keys(localErrors).length) {
    applyFieldErrors(event.currentTarget, localErrors);
    return;
  }

  try {
    await api.register(payload);
    state.authMode = "login";
    state.globalMessage = { tone: "info", text: "Account created successfully. Sign in with your new credentials." };
    render();
  } catch (error) {
    const { formErrors, message } = handleApiError(error, { form: true });
    applyFieldErrors(event.currentTarget, formErrors);
    state.globalMessage = { tone: "error", text: message };
    render();
  }
}

function updatePasswordStrength(password) {
  const meter = document.querySelector(".strength-fill");
  const label = document.querySelector("[data-password-strength-label]");
  if (!meter || !label) return;
  const strength = passwordStrengthMeta(password);
  meter.className = `strength-fill ${strength.className}`;
  meter.style.width = `${strength.width}%`;
  label.textContent = strength.label;
}

async function onTransactionFilterSubmit(event) {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  state.transactions.filters = {
    type: String(formData.get("type") ?? ""),
    category: String(formData.get("category") ?? "").trim(),
    start_date: String(formData.get("start_date") ?? ""),
    end_date: String(formData.get("end_date") ?? ""),
  };
  state.transactions.page = 1;
  await loadTransactions();
}

function resetTransactionFilters() {
  state.transactions.filters = { type: "", category: "", start_date: "", end_date: "" };
  state.transactions.page = 1;
  render();
  loadTransactions();
}

async function startEditTransaction(transactionId) {
  try {
    const transaction = await api.getTransaction(transactionId);
    state.transactions.selectedId = transactionId;
    state.transactions.formMode = "edit";
    state.transactions.formErrors = {};
    state.transactions.formMessage = null;
    state.transactions.items = [
      { ...transaction },
      ...state.transactions.items.filter((item) => item.id !== transactionId),
    ];
    render();
  } catch (error) {
    handleApiError(error);
  }
}

async function onTransactionSubmit(event) {
  event.preventDefault();
  state.transactions.saving = true;
  state.transactions.formErrors = {};
  state.transactions.formMessage = null;
  render();

  const formData = new FormData(event.currentTarget);
  const payload = {
    amount: Number(formData.get("amount")),
    type: String(formData.get("type") ?? ""),
    category: String(formData.get("category") ?? "").trim(),
    date: String(formData.get("date") ?? ""),
    description: String(formData.get("description") ?? "").trim() || null,
  };

  try {
    if (state.transactions.formMode === "edit" && state.transactions.selectedId) {
      await api.updateTransaction(state.transactions.selectedId, payload);
      toast("Transaction updated.", "success");
    } else {
      const userIdRaw = String(formData.get("user_id") ?? "").trim();
      if (userIdRaw) payload.user_id = Number(userIdRaw);
      await api.createTransaction(payload);
      toast("Transaction created.", "success");
    }
    state.transactions.formMode = "create";
    state.transactions.selectedId = null;
    await loadTransactions();
  } catch (error) {
    const { formErrors, message } = handleApiError(error, { form: true });
    state.transactions.formErrors = formErrors;
    state.transactions.formMessage = { tone: "error", text: message };
  } finally {
    state.transactions.saving = false;
    render();
  }
}

async function deleteTransaction(transactionId, returnFocusSelector) {
  openModal({
    title: `Soft-delete transaction #${transactionId}?`,
    body: "This hides the transaction from lists and dashboards. It is not presented as a permanent erase in this system.",
    confirmLabel: "Hide transaction",
    tone: "danger",
    returnFocusSelector,
    action: async () => {
      try {
        await api.deleteTransaction(transactionId);
        if (state.transactions.selectedId === transactionId) {
          state.transactions.formMode = "create";
          state.transactions.selectedId = null;
        }
        toast("Transaction hidden from active views.", "success");
        await loadTransactions();
      } catch (error) {
        handleApiError(error);
      }
    },
  });
}

async function changeUserRole(userId, role) {
  try {
    const updated = await api.updateUserRole(userId, role);
    state.users.items = state.users.items.map((user) => (user.id === userId ? updated : user));
    delete state.users.pendingRoles[userId];
    state.users.rowMessages[userId] = { tone: "success", text: `Role updated to ${titleCase(updated.role)}.` };
    toast(`Role updated for user #${userId}.`, "success");
    render();
  } catch (error) {
    const handled = handleApiError(error, { form: true });
    state.users.rowMessages[userId] = { tone: "error", text: handled.message };
    await loadUsers();
  }
}

async function toggleUserStatus(userId, isCurrentlyActive) {
  const currentUser = getCurrentUser();
  if (currentUser?.id === userId && isCurrentlyActive) {
    toast("You cannot deactivate your own account.", "warning");
    return;
  }
  try {
    const updated = await api.updateUserStatus(userId, !isCurrentlyActive);
    state.users.items = state.users.items.map((user) => (user.id === userId ? updated : user));
    state.users.rowMessages[userId] = {
      tone: "success",
      text: `User is now ${updated.is_active ? "active" : "inactive"}.`,
    };
    toast(`User #${userId} is now ${updated.is_active ? "active" : "inactive"}.`, "success");
    render();
  } catch (error) {
    const handled = handleApiError(error, { form: true });
    state.users.rowMessages[userId] = { tone: "error", text: handled.message };
    await loadUsers();
  }
}

function clearFieldErrors(form) {
  form.querySelectorAll("[data-error-for]").forEach((node) => {
    node.textContent = "";
  });
}

function applyFieldErrors(form, errors) {
  Object.entries(errors).forEach(([field, message]) => {
    const node =
      form.querySelector(`[data-error-for="${CSS.escape(field)}"]`) ||
      form.querySelector(`[data-error-for="${CSS.escape(field.replace(/^query\./, ""))}"]`);
    if (node) node.textContent = message;
  });
}

bootstrap();
