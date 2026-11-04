import React, { useState, useEffect, useCallback, useRef } from 'react';
import { App as CapApp } from '@capacitor/app';
import { Network } from '@capacitor/network';
import { apiClient, getClockOffsetMs } from '../services/apiClient.js';
import { useI18n } from '../context/I18nContext.jsx';

const ReplacementBanner = ({ worker, onNotice, onScheduleUpdated }) => {
  const { t, getFriendlyError } = useI18n();
  const [offers, setOffers] = useState([]);
  const [actionLoading, setActionLoading] = useState(null);
  const [now, setNow] = useState(Date.now());
  const isForegroundRef = useRef(true);
  const pollTimerRef = useRef(null);
  const pollIntervalMsRef = useRef(30000); // starts at 30s, backs off to 60s

  // Ticker for expiry countdown calculation
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const fetchOffers = useCallback(async () => {
    if (!worker?.id || !isForegroundRef.current) return;
    try {
      const res = await apiClient('/roster/my-offers/');
      if (!res.ok) return;
      const data = await res.json();
      const list = Array.isArray(data) ? data : data.results || [];
      const activeOffers = list.filter((o) => o.status === 'OFFERED');
      setOffers(activeOffers);

      // Backoff poll interval if no offers
      if (activeOffers.length === 0) {
        pollIntervalMsRef.current = Math.min(60000, pollIntervalMsRef.current + 10000);
      } else {
        pollIntervalMsRef.current = 30000;
      }
    } catch (err) {
      console.warn('[ReplacementBanner] Fetch warning:', err.message);
    }
  }, [worker?.id]);

  // Foreground tracking via Capacitor App plugin (Amendment 7)
  useEffect(() => {
    let appStateListener;

    try {
      appStateListener = CapApp.addListener('appStateChange', (state) => {
        isForegroundRef.current = state.isActive;
        if (state.isActive) {
          fetchOffers(); // Refresh instantly on resume
        }
      });
    } catch (err) {
      // Fallback to web visibilitychange
    }

    const handleVisibilityChange = () => {
      const isVisible = document.visibilityState === 'visible';
      isForegroundRef.current = isVisible;
      if (isVisible) {
        fetchOffers();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    // Initial fetch
    fetchOffers();

    // Foreground-only recurring polling
    const scheduleNextPoll = () => {
      pollTimerRef.current = setTimeout(() => {
        if (isForegroundRef.current) {
          fetchOffers().finally(scheduleNextPoll);
        } else {
          scheduleNextPoll();
        }
      }, pollIntervalMsRef.current);
    };

    scheduleNextPoll();

    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      appStateListener?.then?.((h) => h.remove?.());
    };
  }, [fetchOffers]);

  // ── 1-Click Accept (Requires Live Connectivity, Never Queued - Amendment 6) ─
  const handleAccept = async (offer) => {
    // 1. Verify live connectivity
    try {
      const status = await Network.getStatus();
      if (!status.connected) {
        onNotice?.(t('reliever_offline_error'), 'error');
        return;
      }
    } catch {
      if (!navigator.onLine) {
        onNotice?.(t('reliever_offline_error'), 'error');
        return;
      }
    }

    setActionLoading(offer.id);
    try {
      const res = await apiClient(`/roster/offers/${offer.id}/accept/`, {
        method: 'POST',
      });
      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        if (res.status === 409) {
          throw new Error(t('error_slot_covered'));
        }
        throw new Error(data.error || 'Failed to accept offer');
      }

      onNotice?.('Shift replacement confirmed! Roster updated. ✅', 'success');
      setOffers((prev) => prev.filter((o) => o.id !== offer.id));
      onScheduleUpdated?.();
    } catch (err) {
      onNotice?.(getFriendlyError(err), 'error');
      fetchOffers();
    } finally {
      setActionLoading(null);
    }
  };

  // ── 1-Click Decline (Requires Live Connectivity) ────────────────
  const handleDecline = async (offer) => {
    try {
      const status = await Network.getStatus();
      if (!status.connected) {
        onNotice?.(t('reliever_offline_error'), 'error');
        return;
      }
    } catch {
      if (!navigator.onLine) {
        onNotice?.(t('reliever_offline_error'), 'error');
        return;
      }
    }

    setActionLoading(offer.id);
    try {
      const res = await apiClient(`/roster/offers/${offer.id}/decline/`, {
        method: 'POST',
        body: JSON.stringify({ reason: 'Worker declined via mobile' }),
      });
      if (res.ok) {
        onNotice?.('Replacement offer declined.', 'info');
        setOffers((prev) => prev.filter((o) => o.id !== offer.id));
      }
    } catch (err) {
      console.warn('[ReplacementBanner] Decline error:', err.message);
    } finally {
      setActionLoading(null);
    }
  };

  if (offers.length === 0) return null;

  return (
    <div style={{ marginBottom: '20px' }}>
      {offers.map((offer) => {
        // Expiry calculation synchronized with server clock offset (Amendment 7)
        const serverNowMs = now + getClockOffsetMs();
        const expiresAtMs = offer.expires_at ? new Date(offer.expires_at).getTime() : serverNowMs + 300000;
        const diffSec = Math.max(0, Math.floor((expiresAtMs - serverNowMs) / 1000));
        const mins = Math.floor(diffSec / 60);
        const secs = diffSec % 60;
        const formattedCountdown = `${mins}m ${secs < 10 ? '0' : ''}${secs}s`;

        const slot = offer.request?.roster_entry || {};
        const siteName = slot.post?.site?.name || offer.society_name || 'Site';
        const postName = slot.post?.name || 'Staff Post';
        const shiftName = slot.shift?.name || 'Shift';

        return (
          <div
            key={offer.id}
            style={{
              background: 'linear-gradient(135deg, rgba(220, 38, 38, 0.25) 0%, rgba(217, 119, 6, 0.25) 100%)',
              border: '2px solid #ef4444',
              borderRadius: '20px',
              padding: '18px 20px',
              color: '#ffffff',
              boxShadow: '0 8px 24px rgba(239, 68, 68, 0.3)',
              marginBottom: '14px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '20px' }}>🚨</span>
                <span style={{ fontSize: '13px', fontWeight: 800, textTransform: 'uppercase', color: '#fca5a5' }}>
                  {t('reliever_banner_title')}
                </span>
              </div>
              <span
                style={{
                  background: 'rgba(0,0,0,0.6)',
                  padding: '4px 10px',
                  borderRadius: '8px',
                  fontSize: '12px',
                  fontWeight: 800,
                  color: diffSec < 60 ? '#fca5a5' : '#fef08a',
                  border: '1px solid rgba(255,255,255,0.2)',
                }}
              >
                ⏱️ {t('reliever_expires_in', { time: formattedCountdown })}
              </span>
            </div>

            <h4 style={{ fontSize: '17px', fontWeight: 800, marginBottom: '4px' }}>
              {postName} • {shiftName}
            </h4>
            <p style={{ fontSize: '13px', color: '#cbd5e1', marginBottom: '16px' }}>
              🏢 {siteName}
            </p>

            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                type="button"
                onClick={() => handleDecline(offer)}
                disabled={actionLoading === offer.id}
                style={{
                  flex: 1,
                  padding: '12px',
                  background: '#1e293b',
                  color: '#cbd5e1',
                  border: '1px solid rgba(255,255,255,0.2)',
                  borderRadius: '12px',
                  fontSize: '14px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  minHeight: '48px',
                }}
              >
                {t('reliever_decline')}
              </button>
              <button
                type="button"
                onClick={() => handleAccept(offer)}
                disabled={actionLoading === offer.id || diffSec <= 0}
                style={{
                  flex: 2,
                  padding: '12px',
                  background: 'linear-gradient(135deg, #059669 0%, #047857 100%)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '12px',
                  fontSize: '14px',
                  fontWeight: 800,
                  cursor: diffSec <= 0 ? 'not-allowed' : 'pointer',
                  minHeight: '48px',
                }}
              >
                {actionLoading === offer.id ? '…' : `✅ ${t('reliever_accept')}`}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default ReplacementBanner;
