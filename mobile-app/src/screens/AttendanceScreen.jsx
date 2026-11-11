import React, { useState, useEffect, useCallback } from 'react';
import altsanLogo from '../assets/altsan-logo.png';
import TaskChecklist from '../components/TaskChecklist.jsx';
import ReplacementBanner from '../components/ReplacementBanner.jsx';
import { apiClient } from '../services/apiClient.js';
import {
  enqueueMutation,
  getItem,
  getItemsForWorker,
  subscribeQueueEvents,
} from '../services/offlineQueue.js';
import { captureInstantLocation, captureCompressedPhoto } from '../services/nativePlugins.js';
import { generateUUID } from '../utils/uuid.js';
import { buildClockInPayload, buildClockOutPayload } from '../services/requestBuilders.js';
import { useI18n } from '../context/I18nContext.jsx';
import './AttendanceScreen.css';

const formatDuration = (hours) => {
  if (!hours && hours !== 0) return '—';
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  return `${h}h ${m}m`;
};

const formatTime = (isoString) => {
  if (!isoString) return '—';
  return new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

const formatDate = (isoString) => {
  if (!isoString) return '—';
  const d = new Date(isoString);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return 'Today';
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return d.toLocaleDateString([], { day: '2-digit', month: 'short' });
};

const computeDistanceMeters = (lat1, lon1, lat2, lon2) => {
  if (lat1 == null || lon1 == null || lat2 == null || lon2 == null) return null;
  const R = 6371000;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(R * c);
};

const AttendanceScreen = ({ worker, onTabChange, onLanguageToggle, locale }) => {
  const { t, getFriendlyError } = useI18n();

  const [activeSlot, setActiveSlot] = useState(null);
  const [schedule, setSchedule] = useState([]);
  const [isClockedIn, setIsClockedIn] = useState(false);
  const [clockInTime, setClockInTime] = useState(null);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [locationText, setLocationText] = useState('Acquiring GPS location…');
  const [gpsCoords, setGpsCoords] = useState({ lat: null, lng: null, accuracy: 10 });
  const [history, setHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [noticeMsg, setNoticeMsg] = useState(null);

  // Queued state tracking
  const [clockInQueued, setClockInQueued] = useState(false);
  const [queuedItemError, setQueuedItemError] = useState(null);
  const [lastSyncedAt, setLastSyncedAt] = useState(null);
  const [pendingQueueCount, setPendingQueueCount] = useState(0);

  // Selfie capture state
  const [capturedSelfie, setCapturedSelfie] = useState(null);
  const [showSelfiePrompt, setShowSelfiePrompt] = useState(false);

  // Live Geofence Distance Calculation
  const distanceToSite =
    activeSlot?.site_latitude != null && gpsCoords?.lat != null
      ? computeDistanceMeters(
          gpsCoords.lat,
          gpsCoords.lng,
          activeSlot.site_latitude,
          activeSlot.site_longitude
        )
      : null;

  const isInsideGeofence =
    distanceToSite != null && activeSlot?.geofence_radius_m != null
      ? distanceToSite <= activeSlot.geofence_radius_m
      : true;

  // Persistent storage inspection (Amendment 5)
  useEffect(() => {
    if (typeof navigator !== 'undefined' && navigator.storage?.persist) {
      navigator.storage.persist().then((granted) => {
        console.log('[Storage] navigator.storage.persist() granted:', granted);
      }).catch((err) => {
        console.warn('[Storage] persist check error:', err);
      });
    }
  }, []);

  // Live clock ticker
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // GPS Acquisition at startup
  useEffect(() => {
    captureInstantLocation().then((coords) => {
      setGpsCoords(coords);
      setLocationText(`${coords.lat.toFixed(4)}, ${coords.lng.toFixed(4)} (±${Math.round(coords.accuracy)}m)`);
    });
  }, []);

  // Sync / Queue Status listener
  const checkQueuedStatus = useCallback(async () => {
    if (!worker?.id) return;
    const items = await getItemsForWorker(worker.id);

    const activeClockIn = items.find(
      (i) => i.action_type === 'CLOCK_IN' && (i.status === 'PENDING' || i.status === 'IN_FLIGHT' || i.status === 'RETRYABLE_ERROR')
    );
    setClockInQueued(Boolean(activeClockIn));

    const pending = items.filter(
      (i) => i.status === 'PENDING' || i.status === 'IN_FLIGHT' || i.status === 'RETRYABLE_ERROR'
    );
    setPendingQueueCount(pending.length);

    const confirmed = items.filter((i) => i.status === 'CONFIRMED' && i.synced_at);
    if (confirmed.length > 0) {
      const latest = [...confirmed].sort((a, b) => new Date(b.synced_at) - new Date(a.synced_at))[0];
      setLastSyncedAt(latest.synced_at);
    }

    const failedItem = items.find(
      (i) => i.status === 'CONFLICT_ERROR' || i.status === 'PERMANENT_ERROR' || i.status === 'DEPENDENCY_HALTED'
    );
    if (failedItem) {
      setQueuedItemError(failedItem.last_error);
    } else {
      setQueuedItemError(null);
    }
  }, [worker?.id]);

  useEffect(() => {
    checkQueuedStatus();
    const unsub = subscribeQueueEvents(checkQueuedStatus);
    return () => unsub();
  }, [checkQueuedStatus]);

  // Load Worker Schedule
  const loadSchedule = useCallback(async () => {
    try {
      const res = await apiClient('/roster/my-schedule/');
      if (!res.ok) return;
      const data = await res.json();
      const slots = Array.isArray(data) ? data : data.results || [];
      setSchedule(slots);

      if (slots.length > 0) {
        const todayStr = new Date().toISOString().slice(0, 10);
        const slot = slots.find((s) => s.date === todayStr || s.status === 'PRESENT' || s.status === 'SCHEDULED');
        if (slot) {
          setActiveSlot(slot);
          if (slot.status === 'PRESENT') {
            setIsClockedIn(true);
          }
        }
      }
    } catch (err) {
      console.warn('[AttendanceScreen] Schedule load error:', err.message);
    }
  }, []);

  // Load Verified Shift History
  const loadHistory = useCallback(async () => {
    try {
      const res = await apiClient('/attendance/my-history/');
      if (!res.ok) return;
      const data = await res.json();
      const records = Array.isArray(data) ? data : data.results || [];
      setHistory(records);

      const active = records.find((r) => r.clock_in && !r.clock_out);
      if (active) {
        setIsClockedIn(true);
        setClockInTime(active.clock_in);
      }
    } catch (err) {
      console.warn('[AttendanceScreen] History load error:', err.message);
    }
  }, []);

  useEffect(() => {
    loadSchedule();
    loadHistory();
  }, [loadSchedule, loadHistory]);

  // ── Native Selfie Capture ──────────────────────────────────────
  const handleTakeSelfie = async () => {
    try {
      const photo = await captureCompressedPhoto({ type: 'SELFIE' });
      setCapturedSelfie(photo);
      setGpsCoords({ lat: photo.lat, lng: photo.lng, accuracy: photo.accuracy });
      setLocationText(`${photo.lat.toFixed(4)}, ${photo.lng.toFixed(4)} (±${Math.round(photo.accuracy)}m)`);
    } catch (err) {
      setError(getFriendlyError(err));
    }
  };

  // ── Clock-In Mutation (Persistent Offline Queue) ───────────────
  const handleClockIn = async () => {
    setIsLoading(true);
    setError(null);
    setNoticeMsg(null);

    const clientUuid = generateUUID();
    const gps = await captureInstantLocation();
    setGpsCoords(gps);

    const payload = buildClockInPayload({
      clockInUuid: clientUuid,
      rosterEntryId: activeSlot?.roster_entry_id,
      lat: gps.lat,
      lng: gps.lng,
      accuracy: gps.accuracy,
      clientTimestamp: new Date().toISOString(),
    });

    try {
      await enqueueMutation({
        client_uuid: clientUuid,
        worker_id: worker.id,
        action_type: 'CLOCK_IN',
        endpoint: '/roster/clock-in/',
        payload,
        roster_entry_id: activeSlot?.roster_entry_id,
        captured_at: payload.client_timestamp,
        is_multipart: Boolean(capturedSelfie),
        file_blob: capturedSelfie?.blob || null,
      });

      // Optimistic local state (Amendment 2)
      setIsClockedIn(true);
      setClockInTime(payload.client_timestamp);
      setClockInQueued(true);
      setNoticeMsg(t('shift_saved_unconfirmed'));
      setShowSelfiePrompt(false);
      setCapturedSelfie(null);
    } catch (err) {
      setError(getFriendlyError(err));
    } finally {
      setIsLoading(false);
    }
  };

  // ── Clock-Out Mutation (Persistent Offline Queue) ──────────────
  const handleClockOut = async () => {
    setIsLoading(true);
    setError(null);
    setNoticeMsg(null);

    const clientUuid = generateUUID();
    const clientTimestamp = new Date().toISOString();
    const payload = buildClockOutPayload({
      clockOutUuid: clientUuid,
      rosterEntryId: activeSlot?.roster_entry_id,
      clientTimestamp,
    });

    try {
      await enqueueMutation({
        client_uuid: clientUuid,
        worker_id: worker.id,
        action_type: 'CLOCK_OUT',
        endpoint: '/roster/clock-out/',
        payload,
        roster_entry_id: activeSlot?.roster_entry_id,
        captured_at: clientTimestamp,
      });

      setIsClockedIn(false);
      setClockInTime(null);
      setNoticeMsg(t('task_status_saved_unconfirmed'));
    } catch (err) {
      setError(getFriendlyError(err));
    } finally {
      setIsLoading(false);
    }
  };

  const handleClockToggle = () => {
    if (isClockedIn) {
      handleClockOut();
    } else {
      if (!isInsideGeofence && distanceToSite != null) {
        setError(`You are ${distanceToSite}m outside the site boundary (Allowed radius: ${activeSlot?.geofence_radius_m || 100}m). Please move inside the property gates to clock in.`);
        return;
      }
      if (!capturedSelfie) {
        setShowSelfiePrompt(true);
        handleTakeSelfie();
      } else {
        handleClockIn();
      }
    }
  };

  return (
    <div className="mobile-app-container">
      <header className="mobile-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <img src={altsanLogo} alt="Altsan" className="header-mini-logo" />
          <h1 style={{ fontSize: '18px', fontWeight: 800 }}>{t('nav_attendance')}</h1>
        </div>
        <button type="button" className="lang-toggle-btn" onClick={onLanguageToggle}>
          🌐 {locale === 'hi' ? 'EN' : 'हिन्दी'}
        </button>
      </header>

      <main className="attendance-main">
        {/* Error / Conflict Alert with Supervisor Instruction */}
        {(error || queuedItemError) && (
          <div className="toast toast-error" role="alert">
            <span>⚠️ {error || queuedItemError}</span>
            <button className="toast-close" onClick={() => { setError(null); setQueuedItemError(null); }}>
              ✕
            </button>
          </div>
        )}

        {noticeMsg && (
          <div className="toast toast-success" role="status">
            <span>{noticeMsg}</span>
          </div>
        )}

        {/* Sync Status & Pending Queue Count Bar (Amendment 5) */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', color: '#94a3b8', margin: '4px 0 14px', padding: '0 4px' }}>
          <span>🔄 {lastSyncedAt ? `${t('last_synced')}: ${formatTime(lastSyncedAt)}` : `${t('last_synced')}: —`}</span>
          {pendingQueueCount > 0 ? (
            <span style={{ color: '#f59e0b', fontWeight: 700 }}>
              ⏳ {pendingQueueCount} {t('queue_pending_badge')}
            </span>
          ) : (
            <span style={{ color: '#10b981', fontWeight: 700 }}>
              ✓ {t('synced_all')}
            </span>
          )}
        </div>

        {/* Real-time Replacement Shift Alert Banner */}
        <ReplacementBanner
          worker={worker}
          onNotice={(msg, type) => {
            if (type === 'error') setError(msg);
            else setNoticeMsg(msg);
          }}
          onScheduleUpdated={() => {
            loadSchedule();
            loadHistory();
          }}
        />

        {/* Live Clock Display */}
        <div className="time-display">
          <h2>{currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</h2>
          <p>{currentTime.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })}</p>
        </div>

        {/* GPS Geofence Status Card */}
        <section className={`location-card ${isInsideGeofence ? 'geofence-in' : 'geofence-out'}`}>
          <div className="location-card-top">
            <div className="location-status-badge">
              <span className={`location-dot ${isInsideGeofence ? 'dot-inside' : 'dot-outside'}`} />
              <strong>{isInsideGeofence ? 'Inside Property Boundary' : 'Outside Boundary'}</strong>
            </div>
            <span className="location-accuracy-pill">±{Math.round(gpsCoords.accuracy || 10)}m GPS</span>
          </div>
          <div className="location-card-body">
            <div className="location-coords-line">📍 {locationText}</div>
            {distanceToSite != null && (
              <div className={`location-distance-hint ${isInsideGeofence ? 'hint-green' : 'hint-red'}`}>
                {isInsideGeofence
                  ? `✓ ${distanceToSite}m from site center (Permitted radius: ${activeSlot?.geofence_radius_m || 100}m)`
                  : `⚠️ ${distanceToSite}m away (Limit: ${activeSlot?.geofence_radius_m || 100}m) — Move inside society gate to clock in`}
              </div>
            )}
          </div>
        </section>

        {/* Assigned Shift Card */}
        {activeSlot ? (
          <section className="job-context-card">
            <div className="job-society-badge">
              <span>🏢 {activeSlot.society_name} • {activeSlot.site_name}</span>
            </div>
            <h3>{t('shift_card_title')}</h3>
            <div className="job-brief">
              <div className="job-primary">
                <strong>{activeSlot.post_name}</strong>
                <span>{activeSlot.shift_name} ({formatTime(activeSlot.shift_start_at)} – {formatTime(activeSlot.shift_end_at)})</span>
              </div>
              {isClockedIn && (
                <div style={{ marginTop: '8px' }}>
                  {clockInQueued ? (
                    <span className="badge-unconfirmed">⏳ {t('shift_saved_unconfirmed')}</span>
                  ) : (
                    <span className="badge-confirmed">🟢 {t('shift_status_active', { time: formatTime(clockInTime) })}</span>
                  )}
                </div>
              )}
            </div>
          </section>
        ) : (
          <section className="job-context-card empty-job">
            <h3>{t('shift_card_title')}</h3>
            <p className="job-hint">{t('shift_card_no_shift')}</p>
          </section>
        )}

        {/* Selfie Verification Modal / Trigger */}
        {showSelfiePrompt && !isClockedIn && (
          <div className="selfie-card">
            <div className="selfie-header">
              <span className="selfie-title">📸 {t('shift_selfie_prompt')}</span>
              <p className="selfie-subtext">Biometric photo evidence required for geofenced clock-in.</p>
            </div>
            {capturedSelfie ? (
              <div className="selfie-preview-wrapper">
                <div className="selfie-circle-box">
                  <img
                    src={capturedSelfie.web_preview}
                    alt="Clock-in Selfie"
                    className="selfie-img"
                  />
                  <div className="selfie-check-icon">✓</div>
                </div>
                <div className="selfie-btn-row">
                  <button
                    type="button"
                    onClick={handleTakeSelfie}
                    className="btn-selfie-retake"
                  >
                    🔄 Retake Photo
                  </button>
                  <button
                    type="button"
                    onClick={handleClockIn}
                    disabled={isLoading}
                    className="btn-selfie-confirm"
                  >
                    {isLoading ? 'Saving…' : '✓ Confirm & Clock In'}
                  </button>
                </div>
              </div>
            ) : (
              <div className="selfie-empty-box">
                <button
                  type="button"
                  onClick={handleTakeSelfie}
                  className="btn-selfie-snap"
                >
                  🤳 {t('shift_selfie_take')}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Main Clock Toggle Button (Sunlight Large Touch Target) */}
        <div className="clock-action">
          <button
            id="clock-toggle-btn"
            className={`clock-btn ${isClockedIn ? 'out' : 'in'} ${isLoading ? 'loading' : ''}`}
            onClick={handleClockToggle}
            disabled={isLoading}
            style={{ minHeight: '80px' }}
          >
            <div className="btn-circle">
              {isLoading ? (
                <div className="spinner" />
              ) : (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                  <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                </svg>
              )}
            </div>
            <span>
              {isLoading
                ? '…'
                : isClockedIn
                ? t('shift_clock_out_btn')
                : t('shift_clock_in_btn')}
            </span>
          </button>
          <p className="clock-hint">
            {isClockedIn
              ? clockInQueued
                ? t('shift_saved_unconfirmed')
                : t('shift_status_active', { time: formatTime(clockInTime) })
              : t('shift_status_ready')}
          </p>
        </div>

        {/* Shift Housekeeping Tasks (Offline Enqueued) */}
        <TaskChecklist
          worker={worker}
          isClockedIn={isClockedIn}
          activeSlot={activeSlot}
          onNotice={(msg, type) => {
            if (type === 'error') setError(msg);
            else setNoticeMsg(msg);
          }}
        />

        {/* Verified Attendance History */}
        <section className="attendance-history" style={{ marginTop: '28px' }}>
          <div className="history-header">
            <h3>Recent Shift Attendance</h3>
            <span className="shift-count">{history.length} verified</span>
          </div>
          <div className="history-list">
            {history.length === 0 && <p className="empty-state">No shift logs found.</p>}
            {history.slice(0, 5).map((rec) => (
              <div className="history-item" key={rec.id || rec.attendance_id || rec.clock_in}>
                <div>
                  <div className="date">{formatDate(rec.clock_in || rec.clock_in_at)}</div>
                  {(rec.society_name || rec.site_name) && (
                    <div className="history-society">🏢 {rec.society_name || rec.site_name}</div>
                  )}
                </div>
                <div className="hours">
                  {formatTime(rec.clock_in || rec.clock_in_at)} – {rec.clock_out || rec.clock_out_at ? formatTime(rec.clock_out || rec.clock_out_at) : '…'}
                </div>
                <div className={`total ${!rec.clock_out && !rec.clock_out_at ? 'active' : ''}`}>
                  {rec.clock_out || rec.clock_out_at ? formatDuration(rec.duration_hours || rec.worked_minutes / 60) : '🟢 Active'}
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>

      {/* Mobile Bottom Navigation */}
      <nav className="mobile-tab-bar">
        <div className="tab-item active" onClick={() => onTabChange?.('attendance')}>
          <div className="tab-icon">🕒</div>
          <span>{t('nav_attendance')}</span>
        </div>
        <div className="tab-item" onClick={() => onTabChange?.('jobs')}>
          <div className="tab-icon">💼</div>
          <span>{t('nav_jobs')}</span>
        </div>
        <div className="tab-item" onClick={() => onTabChange?.('earnings')}>
          <div className="tab-icon">💰</div>
          <span>{t('nav_earnings')}</span>
        </div>
      </nav>
    </div>
  );
};

export default AttendanceScreen;
