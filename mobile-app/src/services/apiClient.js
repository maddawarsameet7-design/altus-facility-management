import { SecureStorage } from './secureStorage.js';

const resolveApiBase = () => {
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_URL) {
    return import.meta.env.VITE_API_URL.replace(/\/+$/, '');
  }
  return 'https://api.altsan.com/api';
};

export const API_BASE = resolveApiBase();

// Clock drift tracker (drift in milliseconds between phone and server)
let serverClockOffsetMs = 0;
let isClockDrifted = false;
const MAX_ALLOWED_DRIFT_MS = 5 * 60 * 1000; // 5 minutes

// Single-flight token refresh promise (Amendment 8)
let activeRefreshPromise = null;

// Clock drift and logout listeners
const authListeners = new Set();
const clockListeners = new Set();

export const subscribeAuthEvents = (listener) => {
  authListeners.add(listener);
  return () => authListeners.delete(listener);
};

export const subscribeClockDrift = (listener) => {
  clockListeners.add(listener);
  return () => clockListeners.delete(listener);
};

export const getClockOffsetMs = () => serverClockOffsetMs;
export const getIsClockDrifted = () => isClockDrifted;
export const setServerClockOffsetForTesting = (offset) => {
  serverClockOffsetMs = offset;
};

/**
 * Inspect Date header from server response to compute clock drift.
 */
const inspectServerDateHeader = (response) => {
  try {
    const serverDateStr = response.headers.get('date');
    if (!serverDateStr) return;
    const serverTimeMs = Date.parse(serverDateStr);
    if (isNaN(serverTimeMs)) return;

    const localTimeMs = Date.now();
    serverClockOffsetMs = serverTimeMs - localTimeMs;
    const drift = Math.abs(serverClockOffsetMs);

    const driftedNow = drift > MAX_ALLOWED_DRIFT_MS;
    if (driftedNow !== isClockDrifted) {
      isClockDrifted = driftedNow;
      clockListeners.forEach((fn) => fn({ isClockDrifted, offsetMs: serverClockOffsetMs }));
    }
  } catch (err) {
    // Non-blocking header parsing
  }
};

/**
 * Single-flight token refresh implementation.
 * Guarantees exactly 1 network call to /api/auth/refresh/ regardless of how many concurrent 401s occur.
 */
export const refreshTokenSingleFlight = async () => {
  if (activeRefreshPromise) {
    return activeRefreshPromise;
  }

  activeRefreshPromise = (async () => {
    try {
      const refreshToken = await SecureStorage.get('refresh_token');
      if (!refreshToken) {
        throw new Error('No refresh token available');
      }

      const res = await fetch(`${API_BASE}/auth/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh: refreshToken }),
      });

      inspectServerDateHeader(res);

      if (!res.ok) {
        throw new Error(`Refresh failed with HTTP ${res.status}`);
      }

      const data = await res.json();
      if (!data.access) {
        throw new Error('Refresh response missing access token');
      }

      await SecureStorage.set('access_token', data.access);
      if (data.refresh) {
        await SecureStorage.set('refresh_token', data.refresh);
      }

      return data.access;
    } catch (err) {
      // Clean wipe of sensitive credentials
      await SecureStorage.clearTokens();
      authListeners.forEach((fn) => fn({ type: 'LOGOUT', reason: 'SESSION_REVOKED_OR_EXPIRED' }));
      throw err;
    } finally {
      activeRefreshPromise = null;
    }
  })();

  return activeRefreshPromise;
};

/**
 * Hardened API request wrapper.
 * Handles auto-authorization, single-flight refresh on 401, server clock offset detection,
 * and safe error redaction.
 */
export const apiClient = async (path, options = {}) => {
  const url = path.startsWith('http') ? path : `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
  const headers = new Headers(options.headers || {});

  // Add auth header if token exists and not already provided
  if (!headers.has('Authorization')) {
    const token = await SecureStorage.get('access_token');
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
  }

  // Set default JSON Content-Type unless body is FormData
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  let response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (networkError) {
    // Network offline or DNS error
    const err = new Error(networkError.message || 'Network request failed');
    err.isNetworkError = true;
    throw err;
  }

  inspectServerDateHeader(response);

  // Handle 401 Unauthorized via single-flight refresh
  if (response.status === 401 && !path.includes('/auth/login') && !path.includes('/auth/refresh')) {
    try {
      const newAccessToken = await refreshTokenSingleFlight();
      headers.set('Authorization', `Bearer ${newAccessToken}`);
      response = await fetch(url, { ...options, headers });
      inspectServerDateHeader(response);
    } catch (refreshErr) {
      const err = new Error('Authentication expired. Please log in again.');
      err.status = 401;
      err.isAuthError = true;
      throw err;
    }
  }

  return response;
};

export default apiClient;
