import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { SecureStorage } from '../src/services/secureStorage.js';
import {
  apiClient,
  refreshTokenSingleFlight,
  subscribeAuthEvents,
  subscribeClockDrift,
  getClockOffsetMs,
  getIsClockDrifted,
} from '../src/services/apiClient.js';

describe('SecureStorage Service', () => {
  beforeEach(async () => {
    await SecureStorage.clearTokens();
  });

  it('stores and retrieves access and refresh tokens securely', async () => {
    await SecureStorage.set('access_token', 'jwt-access-123');
    await SecureStorage.set('refresh_token', 'jwt-refresh-456');

    const access = await SecureStorage.get('access_token');
    const refresh = await SecureStorage.get('refresh_token');

    assert.equal(access, 'jwt-access-123');
    assert.equal(refresh, 'jwt-refresh-456');
  });

  it('removes keys cleanly and clears tokens', async () => {
    await SecureStorage.set('access_token', 'temp-token');
    await SecureStorage.remove('access_token');
    assert.equal(await SecureStorage.get('access_token'), null);

    await SecureStorage.set('access_token', 't1');
    await SecureStorage.set('refresh_token', 't2');
    await SecureStorage.clearTokens();
    assert.equal(await SecureStorage.get('access_token'), null);
    assert.equal(await SecureStorage.get('refresh_token'), null);
  });
});

describe('API Client Single-Flight Refresh & Hardening', () => {
  beforeEach(async () => {
    await SecureStorage.clearTokens();
  });

  it('executes single-flight token refresh when concurrent 401s occur', async () => {
    await SecureStorage.set('access_token', 'expired-access');
    await SecureStorage.set('refresh_token', 'valid-refresh');

    let refreshCallCount = 0;
    const originalFetch = global.fetch;

    global.fetch = async (url, options) => {
      const urlStr = String(url);

      if (urlStr.includes('/auth/refresh')) {
        refreshCallCount++;
        return {
          ok: true,
          status: 200,
          headers: new Headers({ date: new Date().toUTCString() }),
          json: async () => ({ access: 'new-fresh-access-token', refresh: 'new-refresh-token' }),
        };
      }

      // Normal endpoint returns 401 on first try, then 200 on retry with new token
      const authHeader = options?.headers?.get?.('Authorization') || options?.headers?.['Authorization'];
      if (authHeader === 'Bearer new-fresh-access-token') {
        return {
          ok: true,
          status: 200,
          headers: new Headers({ date: new Date().toUTCString() }),
          json: async () => ({ success: true }),
        };
      }

      return {
        ok: false,
        status: 401,
        headers: new Headers({ date: new Date().toUTCString() }),
        json: async () => ({ detail: 'Token expired' }),
      };
    };

    try {
      // Dispatch 3 concurrent requests that all get 401
      const [res1, res2, res3] = await Promise.all([
        apiClient('/roster/my-schedule/'),
        apiClient('/housekeeping/tasks/my-tasks/'),
        apiClient('/user/me/'),
      ]);

      assert.equal(res1.status, 200);
      assert.equal(res2.status, 200);
      assert.equal(res3.status, 200);

      // Crucial Amendment 8: Exactly ONE refresh call occurred despite 3 concurrent 401s!
      assert.equal(refreshCallCount, 1, 'Exactly one single-flight refresh call must be made');
      assert.equal(await SecureStorage.get('access_token'), 'new-fresh-access-token');
    } finally {
      global.fetch = originalFetch;
    }
  });

  it('wipes tokens and emits logout event when refresh fails (revoked session)', async () => {
    await SecureStorage.set('access_token', 'expired-access');
    await SecureStorage.set('refresh_token', 'invalid-revoked-refresh');

    let logoutEmitted = false;
    const unsubscribe = subscribeAuthEvents((event) => {
      if (event.type === 'LOGOUT') logoutEmitted = true;
    });

    const originalFetch = global.fetch;
    global.fetch = async () => ({
      ok: false,
      status: 401,
      headers: new Headers({ date: new Date().toUTCString() }),
      json: async () => ({ detail: 'Token revoked' }),
    });

    try {
      await assert.rejects(
        async () => {
          await apiClient('/roster/my-schedule/');
        },
        (err) => err.status === 401
      );

      assert.equal(logoutEmitted, true);
      assert.equal(await SecureStorage.get('access_token'), null);
      assert.equal(await SecureStorage.get('refresh_token'), null);
    } finally {
      unsubscribe();
      global.fetch = originalFetch;
    }
  });

  it('detects server clock drift from Date header when offset exceeds 5 minutes', async () => {
    let driftNotification = null;
    const unsubscribe = subscribeClockDrift((data) => {
      driftNotification = data;
    });

    // Server date 10 minutes ahead of local phone time
    const futureServerDate = new Date(Date.now() + 10 * 60 * 1000).toUTCString();

    const originalFetch = global.fetch;
    global.fetch = async () => ({
      ok: true,
      status: 200,
      headers: new Headers({ date: futureServerDate }),
      json: async () => ({ ok: true }),
    });

    try {
      await apiClient('/health/');
      assert.equal(getIsClockDrifted(), true);
      assert.ok(Math.abs(getClockOffsetMs()) > 5 * 60 * 1000);
      assert.equal(driftNotification?.isClockDrifted, true);
    } finally {
      unsubscribe();
      global.fetch = originalFetch;
    }
  });
});
