import { openDB } from 'idb';
import { apiClient } from './apiClient.js';

const DB_NAME = 'altsan_worker_offline_db';
const DB_VERSION = 1;
const QUEUE_STORE = 'write_queue';

// In-memory fallback for environments without IndexedDB (e.g., standard Node unit tests)
const memoryQueue = new Map();

export const clearQueueForTesting = async () => {
  memoryQueue.clear();
  if (typeof indexedDB !== 'undefined') {
    const db = await getDB();
    if (db) {
      const tx = db.transaction(QUEUE_STORE, 'readwrite');
      await tx.objectStore(QUEUE_STORE).clear();
    }
  }
};

const isIndexedDBAvailable = () => {
  return typeof indexedDB !== 'undefined';
};

const getDB = async () => {
  if (!isIndexedDBAvailable()) return null;
  return openDB(DB_NAME, DB_VERSION, {
    upgrade(db) {
      if (!db.objectStoreNames.contains(QUEUE_STORE)) {
        const store = db.createObjectStore(QUEUE_STORE, { keyPath: 'id' });
        store.createIndex('worker_id', 'worker_id', { unique: false });
        store.createIndex('status', 'status', { unique: false });
        store.createIndex('rank', 'rank', { unique: false });
      }
    },
  });
};

// Queue event listeners
const queueListeners = new Set();
export const subscribeQueueEvents = (listener) => {
  queueListeners.add(listener);
  return () => queueListeners.delete(listener);
};

const notifyQueueChanged = async (workerId) => {
  const pendingCount = await getPendingCount(workerId);
  queueListeners.forEach((fn) => fn({ workerId, pendingCount }));
};

// Rank ordering definitions (Lower rank executes first)
export const ACTION_RANKS = {
  CLOCK_IN: 1,
  PHOTO_UPLOAD: 2,
  TASK_CLAIM: 3,
  TASK_START: 3,
  TASK_COMPLETE: 4,
  TASK_SKIP: 4,
  CLOCK_OUT: 99,
};

/**
 * Persist queue item to IndexedDB or memory fallback.
 */
export const persistItem = async (item) => {
  const db = await getDB();
  if (db) {
    await db.put(QUEUE_STORE, item);
  } else {
    memoryQueue.set(item.id, { ...item });
  }
};

/**
 * Retrieve queue item by client UUID.
 */
export const getItem = async (id) => {
  const db = await getDB();
  if (db) {
    return (await db.get(QUEUE_STORE, id)) || null;
  }
  return memoryQueue.get(id) || null;
};

/**
 * Retrieve all items for a specific worker.
 */
export const getItemsForWorker = async (workerId) => {
  const db = await getDB();
  if (db) {
    const tx = db.transaction(QUEUE_STORE, 'readonly');
    const store = tx.objectStore(QUEUE_STORE);
    const index = store.index('worker_id');
    const records = await index.getAll(workerId);
    return records || [];
  }
  return Array.from(memoryQueue.values()).filter((item) => item.worker_id === workerId);
};

/**
 * Get count of unconfirmed pending/in-flight items for UI badge.
 */
export const getPendingCount = async (workerId) => {
  const items = await getItemsForWorker(workerId);
  return items.filter(
    (item) => item.status === 'PENDING' || item.status === 'RETRYABLE_ERROR' || item.status === 'IN_FLIGHT'
  ).length;
};

/**
 * Check if worker has unsynced items before logging out.
 */
export const hasPendingItems = async (workerId) => {
  const count = await getPendingCount(workerId);
  return count > 0;
};

/**
 * Enqueue a mutation into the persistent offline queue.
 * Guarantees client UUID reuse, capture timestamping, and dependency ranking.
 */
export const enqueueMutation = async ({
  client_uuid,
  worker_id,
  action_type,
  endpoint,
  method = 'POST',
  payload = {},
  captured_at = new Date().toISOString(),
  roster_entry_id = null,
  is_multipart = false,
  file_blob = null,
  autoFlush = true,
}) => {
  if (!client_uuid) {
    throw new Error('client_uuid is required for offline queue item');
  }
  if (!worker_id) {
    throw new Error('worker_id is required to isolate offline queue data');
  }

  // Idempotent check: if already exists with same uuid, don't overwrite
  const existing = await getItem(client_uuid);
  if (existing) {
    return existing;
  }

  const rank = ACTION_RANKS[action_type] || 5;

  const item = {
    id: client_uuid,
    client_uuid,
    worker_id: String(worker_id),
    action_type,
    endpoint,
    method,
    payload,
    is_multipart: Boolean(is_multipart),
    file_blob: file_blob || null,
    captured_at,
    roster_entry_id: roster_entry_id ? String(roster_entry_id) : null,
    rank,
    status: 'PENDING',
    attempts: 0,
    next_retry_at: 0,
    last_error: null,
    server_response: null,
    created_at: new Date().toISOString(),
  };

  await persistItem(item);
  await notifyQueueChanged(worker_id);

  if (autoFlush) {
    // Non-blocking sync attempt
    flushQueue(worker_id).catch(() => {});
  }

  return item;
};

// Queue mutex lock per worker
let activeFlushPromise = null;

/**
 * Flush and process queue items strictly obeying the dependency DAG.
 */
export const flushQueue = async (workerId) => {
  if (activeFlushPromise) {
    await activeFlushPromise;
  }

  activeFlushPromise = (async () => {
    try {
      const items = await getItemsForWorker(workerId);
      if (!items || items.length === 0) return;

      const nowMs = Date.now();
      const eligibleItems = items.filter((item) => {
        if (
          item.status === 'CONFIRMED' ||
          item.status === 'PERMANENT_ERROR' ||
          item.status === 'CONFLICT_ERROR' ||
          item.status === 'DEPENDENCY_HALTED'
        ) {
          return false;
        }
        if (item.status === 'RETRYABLE_ERROR' && item.next_retry_at > nowMs) {
          return false;
        }
        return true;
      });

      if (eligibleItems.length === 0) return;

      // Sort by rank ASC, then captured_at ASC (Enforces DAG priority)
      eligibleItems.sort((a, b) => {
        if (a.rank !== b.rank) return a.rank - b.rank;
        return new Date(a.captured_at) - new Date(b.captured_at);
      });

      for (const item of eligibleItems) {
        // Refresh items state for fresh DAG verification
        const currentItems = await getItemsForWorker(workerId);

        // ── DAG Ordering Enforcement ──
        // Rule 1: Task actions require Clock-in on that roster entry to be CONFIRMED
        if (item.action_type !== 'CLOCK_IN' && item.roster_entry_id) {
          const clockIn = currentItems.find(
            (other) => other.action_type === 'CLOCK_IN' && other.roster_entry_id === item.roster_entry_id
          );

          if (clockIn) {
            if (clockIn.status === 'PERMANENT_ERROR' || clockIn.status === 'CONFLICT_ERROR') {
              item.status = 'DEPENDENCY_HALTED';
              item.last_error = 'Clock-in failed on server. Dependent actions halted. Please tell your supervisor.';
              await persistItem(item);
              continue;
            }
            if (clockIn.status !== 'CONFIRMED') {
              // Wait for Clock-in to complete first
              continue;
            }
          }
        }

        // Rule 2: Never CLOCK_OUT before CLOCK_IN is CONFIRMED
        if (item.action_type === 'CLOCK_OUT' && item.roster_entry_id) {
          const clockIn = currentItems.find(
            (other) => other.action_type === 'CLOCK_IN' && other.roster_entry_id === item.roster_entry_id
          );
          if (clockIn && clockIn.status !== 'CONFIRMED') {
            continue;
          }
        }

        // Rule 3: For TASK_COMPLETE, any photos queued for that task must be uploaded first
        if (item.action_type === 'TASK_COMPLETE') {
          const taskId = item.payload?.task_id || item.endpoint?.split('/')[4];
          const pendingPhotos = currentItems.filter(
            (other) =>
              other.action_type === 'PHOTO_UPLOAD' &&
              (other.payload?.task_id === taskId || other.endpoint?.includes(taskId)) &&
              other.status !== 'CONFIRMED'
          );
          if (pendingPhotos.length > 0) {
            continue;
          }
        }

        // Execute request
        item.status = 'IN_FLIGHT';
        await persistItem(item);

        try {
          let fetchOptions = {
            method: item.method || 'POST',
          };

          if (item.is_multipart) {
            const formData = new FormData();
            formData.append('client_uuid', item.client_uuid);
            formData.append('captured_at', item.captured_at);
            Object.entries(item.payload || {}).forEach(([k, v]) => {
              formData.append(k, v);
            });
            if (item.file_blob) {
              formData.append('file', item.file_blob, `${item.client_uuid}.jpg`);
            }
            fetchOptions.body = formData;
          } else {
            const bodyPayload = {
              client_uuid: item.client_uuid,
              captured_at: item.captured_at,
              ...(item.payload || {}),
            };
            fetchOptions.body = JSON.stringify(bodyPayload);
          }

          const res = await apiClient(item.endpoint, fetchOptions);
          const data = await res.json().catch(() => ({}));

          // Success: 200 / 201 (or idempotent replay 200)
          if (res.ok) {
            item.status = 'CONFIRMED';
            item.synced_at = new Date().toISOString();
            item.server_response = data;
            item.last_error = null;
            await persistItem(item);
            continue;
          }

          // 409 Conflict: Real domain conflict (Amendment 1)
          if (res.status === 409) {
            item.status = 'CONFLICT_ERROR';
            item.last_error =
              data.error ||
              'Action conflict on server (already covered or occupied). Please tell your supervisor.';
            await persistItem(item);

            if (item.action_type === 'CLOCK_IN' && item.roster_entry_id) {
              await haltDependents(workerId, item.roster_entry_id, item.last_error);
            }
            continue;
          }

          // 400, 403, 404: Permanent rejection
          if (res.status === 400 || res.status === 403 || res.status === 404) {
            item.status = 'PERMANENT_ERROR';
            item.last_error =
              data.error ||
              data.detail ||
              `Server rejected request (HTTP ${res.status}). Please tell your supervisor.`;
            await persistItem(item);

            if (item.action_type === 'CLOCK_IN' && item.roster_entry_id) {
              await haltDependents(workerId, item.roster_entry_id, item.last_error);
            }
            continue;
          }

          // 429 Rate Limit or 5xx Server Error: Retryable with backoff
          throw new Error(data.error || `Server returned HTTP ${res.status}`);
        } catch (err) {
          item.attempts += 1;
          item.status = 'RETRYABLE_ERROR';
          item.last_error = err.message || 'Network error';

          // Exponential backoff with jitter: 2^attempts * 1000ms + random(0-500ms), capped at 60s
          const backoffMs = Math.min(
            60000,
            Math.pow(2, Math.min(item.attempts, 6)) * 1000 + Math.floor(Math.random() * 500)
          );
          item.next_retry_at = Date.now() + backoffMs;

          await persistItem(item);
        }
      }
    } finally {
      await notifyQueueChanged(workerId);
      activeFlushPromise = null;
    }
  })();

  return activeFlushPromise;
};

/**
 * Halt all dependent items when a clock-in encounters a permanent or conflict error.
 */
const haltDependents = async (workerId, rosterEntryId, reason) => {
  const items = await getItemsForWorker(workerId);
  for (const item of items) {
    if (item.roster_entry_id === rosterEntryId && item.action_type !== 'CLOCK_IN') {
      if (item.status === 'PENDING' || item.status === 'RETRYABLE_ERROR') {
        item.status = 'DEPENDENCY_HALTED';
        item.last_error = `Parent clock-in halted: ${reason}`;
        await persistItem(item);
      }
    }
  }
};

export default {
  enqueueMutation,
  flushQueue,
  getItem,
  getItemsForWorker,
  getPendingCount,
  hasPendingItems,
  subscribeQueueEvents,
  clearQueueForTesting,
};
