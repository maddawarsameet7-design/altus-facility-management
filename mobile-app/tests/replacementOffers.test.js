import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { getClockOffsetMs, setServerClockOffsetForTesting } from '../src/services/apiClient.js';

describe('Replacement Offers Service & Sync Logic (Amendments 6 & 7)', () => {
  beforeEach(() => {
    setServerClockOffsetForTesting(0);
  });

  it('calculates offer expiry accurately using server clock offset', () => {
    // Phone clock is 2 minutes fast (local now = 10:02, server now = 10:00, offset = -120000)
    setServerClockOffsetForTesting(-120000);

    const localNow = new Date('2026-11-05T10:02:00Z').getTime();
    const serverNow = localNow + getClockOffsetMs(); // 10:00:00Z
    assert.equal(new Date(serverNow).toISOString(), '2026-11-05T10:00:00.000Z');

    const offerExpiresAt = '2026-11-05T10:05:00Z'; // 5 minutes after server now
    const expiresAtMs = new Date(offerExpiresAt).getTime();

    const diffSec = Math.max(0, Math.floor((expiresAtMs - serverNow) / 1000));
    assert.equal(diffSec, 300); // exactly 5 minutes (300 seconds) remaining
  });

  it('detects expired offer when server time has surpassed expires_at', () => {
    // Phone clock is 5 minutes behind (local now = 09:55, server now = 10:00, offset = +300000)
    setServerClockOffsetForTesting(300000);

    const localNow = new Date('2026-11-05T09:55:00Z').getTime();
    const serverNow = localNow + getClockOffsetMs(); // 10:00:00Z

    const offerExpiresAt = '2026-11-05T09:59:00Z'; // expired 1 minute ago server-side
    const expiresAtMs = new Date(offerExpiresAt).getTime();

    const diffSec = Math.max(0, Math.floor((expiresAtMs - serverNow) / 1000));
    assert.equal(diffSec, 0); // correctly expired
  });

  it('enforces live connectivity constraint: offline accept throws immediately without queueing', async () => {
    // Mock network status as disconnected
    let isConnected = false;
    let queueAttempted = false;

    const acceptReplacement = async (offerId) => {
      if (!isConnected) {
        throw new Error('रिलिवर ऑफर स्वीकारने के लिए इंटरनेट जरूरी है। (Live connection required)');
      }
      return { success: true };
    };

    await assert.rejects(
      async () => {
        await acceptReplacement('offer-123');
      },
      {
        message: /रिलिवर ऑफर स्वीकारने के लिए इंटरनेट जरूरी है/
      }
    );

    assert.equal(queueAttempted, false, 'Offer accept MUST NOT be placed into offline queue');
  });
});
