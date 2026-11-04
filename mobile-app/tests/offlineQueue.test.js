import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import {
  enqueueMutation,
  flushQueue,
  getItem,
  getItemsForWorker,
  getPendingCount,
  hasPendingItems,
  clearQueueForTesting,
} from '../src/services/offlineQueue.js';

describe('Persistent Offline Queue Service', () => {
  const worker1 = 'worker_uuid_101';
  const worker2 = 'worker_uuid_202';
  const rosterSlot1 = 'roster_entry_aaa';

  beforeEach(async () => {
    await clearQueueForTesting();
  });

  it('guarantees ordering DAG: Clock-in executes before task actions', async () => {
    const executedActions = [];
    const originalFetch = global.fetch;

    global.fetch = async (url) => {
      const urlStr = String(url);
      if (urlStr.includes('/roster/clock-in/')) {
        executedActions.push('CLOCK_IN');
        return {
          ok: true,
          status: 200,
          headers: new Headers(),
          json: async () => ({ id: 'event_1', status: 'PRESENT' }),
        };
      }
      if (urlStr.includes('/tasks/')) {
        executedActions.push('TASK_CLAIM');
        return {
          ok: true,
          status: 200,
          headers: new Headers(),
          json: async () => ({ id: 'task_1', status: 'IN_PROGRESS' }),
        };
      }
      return { ok: true, status: 200, headers: new Headers(), json: async () => ({}) };
    };

    try {
      // Intentionally enqueue task claim BEFORE clock in to test DAG priority re-ordering
      await enqueueMutation({
        client_uuid: 'task_claim_uuid_1',
        worker_id: worker1,
        action_type: 'TASK_CLAIM',
        endpoint: '/housekeeping/tasks/task_1/claim/',
        roster_entry_id: rosterSlot1,
        captured_at: new Date(Date.now() + 5000).toISOString(),
        autoFlush: false,
      });

      await enqueueMutation({
        client_uuid: 'clock_in_uuid_1',
        worker_id: worker1,
        action_type: 'CLOCK_IN',
        endpoint: '/roster/clock-in/',
        roster_entry_id: rosterSlot1,
        captured_at: new Date().toISOString(),
        autoFlush: false,
      });

      await flushQueue(worker1);

      assert.deepEqual(executedActions, ['CLOCK_IN', 'TASK_CLAIM']);
      const clockInItem = await getItem('clock_in_uuid_1');
      const taskClaimItem = await getItem('task_claim_uuid_1');

      assert.equal(clockInItem.status, 'CONFIRMED');
      assert.equal(taskClaimItem.status, 'CONFIRMED');
    } finally {
      global.fetch = originalFetch;
    }
  });

  it('never executes CLOCK_OUT before CLOCK_IN is confirmed', async () => {
    const executedActions = [];
    const originalFetch = global.fetch;

    global.fetch = async (url) => {
      const urlStr = String(url);
      if (urlStr.includes('/clock-in')) {
        executedActions.push('CLOCK_IN');
      } else if (urlStr.includes('/clock-out')) {
        executedActions.push('CLOCK_OUT');
      }
      return { ok: true, status: 200, headers: new Headers(), json: async () => ({}) };
    };

    try {
      await enqueueMutation({
        client_uuid: 'clock_out_uuid_x',
        worker_id: worker1,
        action_type: 'CLOCK_OUT',
        endpoint: '/roster/clock-out/',
        roster_entry_id: 'slot_99',
        autoFlush: false,
      });

      await enqueueMutation({
        client_uuid: 'clock_in_uuid_x',
        worker_id: worker1,
        action_type: 'CLOCK_IN',
        endpoint: '/roster/clock-in/',
        roster_entry_id: 'slot_99',
        autoFlush: false,
      });

      await flushQueue(worker1);

      assert.deepEqual(executedActions, ['CLOCK_IN', 'CLOCK_OUT']);
    } finally {
      global.fetch = originalFetch;
    }
  });

  it('halts with CONFLICT_ERROR on 409 and halts dependent shift items', async () => {
    const originalFetch = global.fetch;

    global.fetch = async (url) => {
      const urlStr = String(url);
      if (urlStr.includes('/clock-in')) {
        return {
          ok: false,
          status: 409,
          headers: new Headers(),
          json: async () => ({ error: 'This slot has been reassigned to a replacement worker.' }),
        };
      }
      return { ok: true, status: 200, headers: new Headers(), json: async () => ({}) };
    };

    try {
      await enqueueMutation({
        client_uuid: 'clock_in_conflict_1',
        worker_id: worker1,
        action_type: 'CLOCK_IN',
        endpoint: '/roster/clock-in/',
        roster_entry_id: 'slot_covered_1',
        autoFlush: false,
      });

      await enqueueMutation({
        client_uuid: 'task_on_covered_slot',
        worker_id: worker1,
        action_type: 'TASK_START',
        endpoint: '/housekeeping/tasks/t2/start/',
        roster_entry_id: 'slot_covered_1',
        autoFlush: false,
      });

      await flushQueue(worker1);

      const clockIn = await getItem('clock_in_conflict_1');
      const task = await getItem('task_on_covered_slot');

      assert.equal(clockIn.status, 'CONFLICT_ERROR');
      assert.ok(clockIn.last_error.includes('replacement worker'));

      // Crucial Amendment 3: Dependent items on this slot are halted!
      assert.equal(task.status, 'DEPENDENCY_HALTED');
      assert.ok(task.last_error.includes('halted'));
    } finally {
      global.fetch = originalFetch;
    }
  });

  it('retries with exponential backoff on network failures and 5xx errors', async () => {
    const originalFetch = global.fetch;

    global.fetch = async () => {
      return {
        ok: false,
        status: 503,
        headers: new Headers(),
        json: async () => ({ error: 'Service Unavailable' }),
      };
    };

    try {
      await enqueueMutation({
        client_uuid: 'retry_backoff_uuid',
        worker_id: worker1,
        action_type: 'TASK_CLAIM',
        endpoint: '/housekeeping/tasks/t5/claim/',
        autoFlush: false,
      });

      await flushQueue(worker1);

      const item = await getItem('retry_backoff_uuid');
      assert.equal(item.status, 'RETRYABLE_ERROR');
      assert.equal(item.attempts, 1);
      assert.ok(item.next_retry_at > Date.now());
    } finally {
      global.fetch = originalFetch;
    }
  });

  it('isolates queue items per worker ID and prevents cross-worker pollution', async () => {
    await enqueueMutation({
      client_uuid: 'w1_task',
      worker_id: worker1,
      action_type: 'TASK_CLAIM',
      endpoint: '/t/1',
      autoFlush: false,
    });

    await enqueueMutation({
      client_uuid: 'w2_task',
      worker_id: worker2,
      action_type: 'TASK_CLAIM',
      endpoint: '/t/2',
      autoFlush: false,
    });

    const w1Items = await getItemsForWorker(worker1);
    const w2Items = await getItemsForWorker(worker2);

    assert.equal(w1Items.some((i) => i.id === 'w1_task'), true);
    assert.equal(w1Items.some((i) => i.id === 'w2_task'), false);

    assert.equal(w2Items.some((i) => i.id === 'w2_task'), true);
    assert.equal(w2Items.some((i) => i.id === 'w1_task'), false);
  });

  it('warns when worker has pending items before logout', async () => {
    await enqueueMutation({
      client_uuid: 'pending_item_1',
      worker_id: worker1,
      action_type: 'TASK_CLAIM',
      endpoint: '/t/1',
      autoFlush: false,
    });

    assert.equal(await hasPendingItems(worker1), true);
    assert.ok((await getPendingCount(worker1)) > 0);
  });
});
