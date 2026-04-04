const runtimeConfig = window.__FINANCE_APP_CONFIG__ ?? {};

export const config = {
  apiBaseUrl: (runtimeConfig.apiBaseUrl ?? "").replace(/\/$/, ""),
  apiV1Prefix: runtimeConfig.apiV1Prefix ?? "/api",
  today: new Date().toISOString().slice(0, 10),
  storageKey: "zorvyn.finance.session",
};

export function buildApiUrl(path) {
  return `${config.apiBaseUrl}${config.apiV1Prefix}${path}`;
}
