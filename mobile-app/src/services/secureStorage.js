import { Capacitor } from '@capacitor/core';
import { SecureStoragePlugin } from 'capacitor-secure-storage-plugin';

/**
 * Keystore-backed secure storage service.
 * Uses Android Keystore (EncryptedSharedPreferences via MasterKeys AES-256-GCM) on native Android.
 * Memory/Session fallback in browser dev/testing environments where native Keystore is unavailable.
 */

// Memory fallback for browser testing & node unit test environment
const memoryStore = new Map();

const isNative = () => Capacitor.isNativePlatform();

export const SecureStorage = {
  async set(key, value) {
    if (!key) return;
    const strVal = typeof value === 'string' ? value : JSON.stringify(value);
    if (isNative()) {
      try {
        await SecureStoragePlugin.set({ key, value: strVal });
        return;
      } catch (err) {
        console.warn(`[SecureStorage] Native set failed for ${key}, falling back to memory store:`, err.message);
      }
    }
    memoryStore.set(key, strVal);
  },

  async get(key) {
    if (!key) return null;
    if (isNative()) {
      try {
        const result = await SecureStoragePlugin.get({ key });
        return result.value ?? null;
      } catch (err) {
        // Plugin rejects if key not found
        return memoryStore.get(key) || null;
      }
    }
    return memoryStore.get(key) || null;
  },

  async remove(key) {
    if (!key) return;
    if (isNative()) {
      try {
        await SecureStoragePlugin.remove({ key });
      } catch (err) {
        // Ignore if already deleted
      }
    }
    memoryStore.delete(key);
  },

  async clearTokens() {
    await this.remove('access_token');
    await this.remove('refresh_token');
    await this.remove('worker_profile');
    memoryStore.clear();
  },
};

export default SecureStorage;
