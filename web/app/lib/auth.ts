/**
 * Authentication utilities
 */

const TOKEN_KEY = "postbox-auth-token";
const USER_ID_KEY = "postbox-user-id";

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getUserId(): number | null {
  if (typeof window === "undefined") return null;
  const id = localStorage.getItem(USER_ID_KEY);
  return id ? parseInt(id, 10) : null;
}

export function setAuthToken(token: string, userId: number): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_ID_KEY, String(userId));
}

export function clearAuth(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_ID_KEY);
}

export function isAuthenticated(): boolean {
  return getAuthToken() !== null;
}
