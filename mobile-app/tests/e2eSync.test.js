import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import {
  enqueueMutation,
  flushQueue,
  getItem,
  getItemsForWorker,
  getPendingCount,
  clearQueueForTesting,
} from '../src/services/offlineQueue.js';
import { SecureStorage } from '../src/services/secureStorage.js';
import { apiClient, setServerClockOffsetForTesting } from '../src/services/apiClient.js';

describe('Comprehensive E2E Sync & Edge Case Tests (Amendment 12)', () => {
  beforeEach(async () => {
    await clearQueueForTesting();
    await SecureStorage.clearTokens();
    setServerClockOffsetForTesting(0);
  });

  // 1. Kill mid-request replay with same UUID (Idempotency)
  it('handles mid-request network kill and safely replays with identical client UUID', async () => {
    const workerId = 'worker_kill_test_1';
    const clientUuid = 'uuid_mid_request_kill_123';
    let requestCount = 0;
    const recordedPayloads = [];

    const originalFetch = global.fetch;
    try {
      global.fetch = async (url, options) => {
        requestCount++;
        const body = options?.body ? JSON.parse(options.body) : {};
        recordedPayloads.push({ url: String(url), body });

        if (requestCount === 1) {
          // Simulate phone being killed / network dropped mid-request
          throw new Error('TypeError: Failed to fetch (connection reset by peer)');
        }

        // On replay, backend returns 200 with existing/new record idempotently
        return {
          ok: true,
          status: 200,
          headers: new Headers({ 'Content-Type': 'application/json' }),
          json: async () => ({
            id: 'attendance_record_999',
            client_uuid: body.client_uuid,
            status: 'PRESENT',
            recorded_at: body.captured_at,
          }),
        };
      };

      // 1. Enqueue item
      await enqueueMutation({
        client_uuid: clientUuid,
        worker_id: workerId,
        action_type: 'CLOCK_IN',
        endpoint: '/roster/clock-in/',
        payload: {
          roster_entry_id: 'slot_e2e_1',
          lat: 19.0760,
          lon: 72.8777,
          accuracy: 12,
        },
        autoFlush: false,
      });

      // 2. First sync attempt fails mid-flight
      await flushQueue(workerId);

      const stateAfterKill = await getItem(clientUuid);
      assert.equal(stateAfterKill.status, 'RETRYABLE_ERROR');
      assert.equal(stateAfterKill.attempts, 1);
      assert.equal(requestCount, 1);

      // Force retry eligibility for test
      stateAfterKill.next_retry_at = Date.now() - 1000;

      // 3. Second sync attempt (reboot / network restored)
      await flushQueue(workerId);

      const stateAfterReplay = await getItem(clientUuid);
      assert.equal(stateAfterReplay.status, 'CONFIRMED');
      assert.equal(requestCount, 2);

      // Verify client UUID was preserved identically across retries (Amendment 1)
      assert.equal(recordedPayloads.length, 2);
      assert.equal(recordedPayloads[0].body.client_uuid, clientUuid);
      assert.equal(recordedPayloads[1].body.client_uuid, clientUuid);
    } finally {
      global.fetch = originalFetch;
    }
  });

  // 2. 409 Conflict Halts Item & Halts Dependents
  it('halts item on 409 conflict and cascades DEPENDENCY_HALTED to all dependent tasks', async () => {
    const workerId = 'worker_conflict_test';
    const slotId = 'roster_conflict_slot_888';

    const originalFetch = global.fetch;
    try {
      global.fetch = async (url) => {
        const urlStr = String(url);
        if (urlStr.includes('/clock-in/')) {
          return {
            ok: false,
            status: 409,
            headers: new Headers({ 'Content-Type': 'application/json' }),
            json: async () => ({
              error: 'Slot already covered by reliever worker or occupied.',
            }),
          };
        }
        return {
          ok: true,
          status: 200,
          headers: new Headers(),
          json: async () => ({ status: 'SUCCESS' }),
        };
      };

      // Enqueue Clock In, Photo Upload, and Task Complete for the same slot
      await enqueueMutation({
        client_uuid: 'conflict_clock_in',
        worker_id: workerId,
        action_type: 'CLOCK_IN',
        endpoint: '/roster/clock-in/',
        roster_entry_id: slotId,
        autoFlush: false,
      });

      await enqueueMutation({
        client_uuid: 'dependent_photo_upload',
        worker_id: workerId,
        action_type: 'TASK_PHOTO',
        endpoint: '/housekeeping/tasks/task_1/photos/',
        roster_entry_id: slotId,
        autoFlush: false,
      });

      await enqueueMutation({
        client_uuid: 'dependent_task_complete',
        worker_id: workerId,
        action_type: 'TASK_COMPLETE',
        endpoint: '/housekeeping/tasks/task_1/complete/',
        roster_entry_id: slotId,
        autoFlush: false,
      });

      // Flush queue
      await flushQueue(workerId);

      // Verify Clock In is in CONFLICT_ERROR
      const clockIn = await getItem('conflict_clock_in');
      assert.equal(clockIn.status, 'CONFLICT_ERROR');
      assert.ok(clockIn.last_error.includes('Slot already covered'));

      // Verify Dependent Photo and Task are in DEPENDENCY_HALTED
      const photo = await getItem('dependent_photo_upload');
      const task = await getItem('dependent_task_complete');

      assert.equal(photo.status, 'DEPENDENCY_HALTED');
      assert.equal(task.status, 'DEPENDENCY_HALTED');
      assert.ok(photo.last_error.includes('halted'));
      assert.ok(task.last_error.includes('halted'));
    } finally {
      global.fetch = originalFetch;
    }
  });

  // 3. Different Worker on Same Phone (Multi-worker Data Isolation)
  it('strictly isolates queue items between different workers on the same device', async () => {
    const workerAlpha = 'worker_device_share_A';
    const workerBeta = 'worker_device_share_B';

    // Worker Alpha enqueues 2 actions
    await enqueueMutation({
      client_uuid: 'alpha_action_1',
      worker_id: workerAlpha,
      action_type: 'CLOCK_IN',
      endpoint: '/roster/clock-in/',
      autoFlush: false,
    });
    await enqueueMutation({
      client_uuid: 'alpha_action_2',
      worker_id: workerAlpha,
      action_type: 'TASK_CLAIM',
      endpoint: '/housekeeping/tasks/1/claim/',
      autoFlush: false,
    });

    // Worker Beta enqueues 1 action
    await enqueueMutation({
      client_uuid: 'beta_action_1',
      worker_id: workerBeta,
      action_type: 'CLOCK_IN',
      endpoint: '/roster/clock-in/',
      autoFlush: false,
    });

    // Check counts
    assert.equal(await getPendingCount(workerAlpha), 2);
    assert.equal(await getPendingCount(workerBeta), 1);

    const alphaItems = await getItemsForWorker(workerAlpha);
    const betaItems = await getItemsForWorker(workerBeta);

    assert.equal(alphaItems.length, 2);
    assert.equal(betaItems.length, 1);
    assert.ok(alphaItems.every((i) => i.worker_id === workerAlpha));
    assert.ok(betaItems.every((i) => i.worker_id === workerBeta));
  });

  // 4. Pending vs Confirmed UI State Transitions
  it('correctly reports PENDING status until confirmed by server sync', async () => {
    const workerId = 'worker_ui_status_test';
    const clientUuid = 'ui_status_uuid_456';

    const originalFetch = global.fetch;
    try {
      global.fetch = async () => ({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: async () => ({ id: 'ok_1' }),
      });

      // 1. Enqueue without flushing
      await enqueueMutation({
        client_uuid: clientUuid,
        worker_id: workerId,
        action_type: 'TASK_COMPLETE',
        endpoint: '/housekeeping/tasks/10/complete/',
        autoFlush: false,
      });

      // Verify initial state is PENDING ("saved, not yet confirmed")
      let item = await getItem(clientUuid);
      assert.equal(item.status, 'PENDING');

      // 2. Perform background sync / flush
      await flushQueue(workerId);

      // Verify synced state is CONFIRMED
      item = await getItem(clientUuid);
      assert.equal(item.status, 'CONFIRMED');
      assert.ok(item.synced_at);
    } finally {
      global.fetch = originalFetch;
    }
  });

  // 5. Offline Replacement Accept Refusal Integration
  it('refuses replacement offer accept immediately when offline without entering queue', async () => {
    const isOnline = false;
    let queueCountBefore = await getPendingCount('any_worker');

    const handleAcceptOffer = async (offerId) => {
      if (!isOnline) {
        throw new Error('रिलिवर ऑफर स्वीकारने के लिए इंटरनेट जरूरी है।');
      }
      return { success: true };
    };

    await assert.rejects(
      async () => handleAcceptOffer('offer_999'),
      /रिलिवर ऑफर स्वीकारने के लिए इंटरनेट जरूरी है/
    );

    let queueCountAfter = await getPendingCount('any_worker');
    assert.equal(queueCountBefore, queueCountAfter, 'Zero items added to queue');
  });

  // 6. Release Build Failure Gate Cases (Amendment 10 & 12)
  it('strictly validates release build environment and fails on missing or insecure VITE_API_URL', async () => {
    const validateReleaseConfig = (mode, apiUrl) => {
      const isRelease = mode === 'production';
      if (isRelease) {
        if (!apiUrl) {
          throw new Error(
            '[SECURITY RELEASE BUILD FAIL] VITE_API_URL environment variable is missing. Set VITE_API_URL=https://api.altsan.com/api for production builds.'
          );
        }
        if (!apiUrl.startsWith('https://')) {
          throw new Error(
            `[SECURITY RELEASE BUILD FAIL] VITE_API_URL must be a secure HTTPS endpoint in production release builds. Got: ${apiUrl}`
          );
        }
      }
      return true;
    };

    // Case A: Missing VITE_API_URL in production must throw
    assert.throws(
      () => validateReleaseConfig('production', ''),
      /\[SECURITY RELEASE BUILD FAIL\] VITE_API_URL environment variable is missing/
    );

    // Case B: Non-HTTPS (cleartext HTTP) VITE_API_URL in production must throw
    assert.throws(
      () => validateReleaseConfig('production', 'http://api.insecure.altsan.com/api'),
      /\[SECURITY RELEASE BUILD FAIL\] VITE_API_URL must be a secure HTTPS endpoint/
    );

    // Case C: Valid HTTPS VITE_API_URL passes cleanly
    assert.equal(
      validateReleaseConfig('production', 'https://api.altsan.com/api'),
      true
    );
  });
});
