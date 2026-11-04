import React, { useState, useEffect, useCallback } from 'react';

const ReplacementBanner = ({ apiBase, authHeaders, onNotice, onScheduleUpdated }) => {
  const [offers, setOffers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(null);
  const [now, setNow] = useState(Date.now());

  // Clock ticker for expiry countdowns
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const fetchOffers = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/roster/my-offers/`, {
        headers: authHeaders(),
      });
      if (!res.ok) return;
      const data = await res.json();
      const list = Array.isArray(data) ? data : data.results || [];
      setOffers(list.filter((o) => o.status === 'OFFERED'));
    } catch (err) {
      console.warn('Replacement offer fetch warning:', err.message);
    }
  }, [apiBase, authHeaders]);

  useEffect(() => {
    fetchOffers();
    const interval = setInterval(fetchOffers, 15000); // 15s poll
    return () => clearInterval(interval);
  }, [fetchOffers]);

  const handleAccept = async (offer) => {
    setActionLoading(offer.id);
    try {
      const res = await fetch(`${apiBase}/roster/offers/${offer.id}/accept/`, {
        method: 'POST',
        headers: authHeaders(),
      });
      const data = await res.json();
      if (!res.ok) {
        if (res.status === 409) {
          throw new Error('This shift has already been claimed by another worker.');
        }
        throw new Error(data.error || 'Failed to accept offer.');
      }
      onNotice?.('Shift replacement confirmed! Roster updated. ✅', 'success');
      setOffers((prev) => prev.filter((o) => o.id !== offer.id));
      onScheduleUpdated?.();
    } catch (err) {
      onNotice?.(err.message, 'error');
      fetchOffers();
    } finally {
      setActionLoading(null);
    }
  };

  const handleDecline = async (offer) => {
    setActionLoading(offer.id);
    try {
      const res = await fetch(`${apiBase}/roster/offers/${offer.id}/decline/`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ reason: 'Worker declined via mobile' }),
      });
      if (res.ok) {
        onNotice?.('Replacement offer declined.', 'info');
        setOffers((prev) => prev.filter((o) => o.id !== offer.id));
      }
    } catch (err) {
      console.warn('Decline error:', err.message);
    } finally {
      setActionLoading(null);
    }
  };

  if (offers.length === 0) return null;

  return (
    <div style={{ marginBottom: '20px' }}>
      {offers.map((offer) => {
        const expiresAt = offer.expires_at ? new Date(offer.expires_at).getTime() : now + 300000;
        const diffSec = Math.max(0, Math.floor((expiresAt - now) / 1000));
        const mins = Math.floor(diffSec / 60);
        const secs = diffSec % 60;
        const formattedCountdown = `${mins}m ${secs < 10 ? '0' : ''}${secs}s`;

        const slot = offer.request?.roster_entry || {};
        const siteName = slot.post?.site?.name || offer.society_name || 'Society Site';
        const postName = slot.post?.name || 'Staff Post';
        const shiftName = slot.shift?.name || 'Scheduled Shift';

        return (
          <div
            key={offer.id}
            style={{
              background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(245, 158, 11, 0.15) 100%)',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              borderRadius: '20px',
              padding: '18px 20px',
              color: '#f8fafc',
              boxShadow: '0 8px 24px rgba(239, 68, 68, 0.2)',
              position: 'relative',
              overflow: 'hidden',
              marginBottom: '12px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '18px' }}>🚨</span>
                <span style={{ fontSize: '12px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.5px', color: '#f87171' }}>
                  Urgent Reliever Shift
                </span>
              </div>
              <span
                style={{
                  background: 'rgba(0,0,0,0.4)',
                  padding: '3px 8px',
                  borderRadius: '6px',
                  fontSize: '11px',
                  fontWeight: 700,
                  color: diffSec < 60 ? '#fca5a5' : '#fde047',
                }}
              >
                ⏱️ {formattedCountdown}
              </span>
            </div>

            <h4 style={{ fontSize: '16px', fontWeight: 800, marginBottom: '4px' }}>
              {postName} • {shiftName}
            </h4>
            <p style={{ fontSize: '13px', color: '#cbd5e1', marginBottom: '14px' }}>
              🏢 {siteName} {offer.society_name && `(${offer.society_name})`}
            </p>

            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                onClick={() => handleDecline(offer)}
                disabled={actionLoading === offer.id}
                style={{
                  flex: 1,
                  padding: '12px',
                  background: '#1e293b',
                  color: '#94a3b8',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '12px',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Decline
              </button>
              <button
                onClick={() => handleAccept(offer)}
                disabled={actionLoading === offer.id || diffSec <= 0}
                style={{
                  flex: 2,
                  padding: '12px',
                  background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '12px',
                  fontSize: '13px',
                  fontWeight: 800,
                  cursor: diffSec <= 0 ? 'not-allowed' : 'pointer',
                  boxShadow: '0 4px 12px rgba(16, 185, 129, 0.3)',
                }}
              >
                {actionLoading === offer.id ? 'Claiming…' : 'Accept Reliever Shift →'}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default ReplacementBanner;
