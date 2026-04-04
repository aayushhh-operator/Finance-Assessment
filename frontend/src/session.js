import { config } from "./config.js";

let memorySession = loadSession();

function loadSession() {
  try {
    const raw = localStorage.getItem(config.storageKey);
    return raw ? JSON.parse(raw) : { token: null, user: null };
  } catch {
    return { token: null, user: null };
  }
}

function saveSession(nextSession) {
  memorySession = nextSession;
  localStorage.setItem(config.storageKey, JSON.stringify(nextSession));
}

export function getSession() {
  return memorySession;
}

export function setToken(token) {
  saveSession({ ...memorySession, token });
}

export function setUser(user) {
  saveSession({ ...memorySession, user });
}

export function clearSession() {
  saveSession({ token: null, user: null });
}

export function isAuthenticated() {
  return Boolean(memorySession?.token);
}
