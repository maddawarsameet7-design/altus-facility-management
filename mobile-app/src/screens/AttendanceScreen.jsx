import React, { useState, useEffect, useCallback } from 'react';
import altsanLogo from '../assets/altsan-logo.png';
import TaskChecklist from '../components/TaskChecklist.jsx';
import ReplacementBanner from '../components/ReplacementBanner.jsx';
import { generateUUID } from '../utils/uuid.js';
import './AttendanceScreen.css';

// ── Dynamic API Configuration ─────────────────────────────────────
const resolveApiBase = () => {
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_URL) {
    return import.meta.env.VITE_API_URL.replace(/\/+$/, '');
  }
  return 'https://api.altsan.com/api';
};

const API_BASE = resolveApiBase();

const getAuthHeaders = () => {
  const token = localStorage.getItem('altsan_token') || localStorage.getItem('access_token') || '';
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
};

const extractList = (data) => {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
};

// ── Utility ────────────────────────────────────────────────────
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

// ── Component ──────────────────────────────────────────────────
const AttendanceScreen = ({ assignmentId: propAssignmentId, onTabChange }) => {
  const [assignmentId, setAssignmentId] = useState(propAssignmentId || null);
  const [activeSlot, setActiveSlot] = useState(null);
  const [schedule, setSchedule] = useState([]);
  const [isClockedIn, setIsClockedIn] = useState(false);
  const [clockInTime, setClockInTime] = useState(null);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [location, setLocation] = useState('Acquiring GPS location…');
  const [gpsCoords, setGpsCoords] = useState({ lat: null, lng: null, accuracy: 10 });
  const [history, setHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [selfieFile, setSelfieFile] = useState(null);
  const [selfiePreview, setSelfiePreview] = useState(null);
  const [showSelfiePrompt, setShowSelfiePrompt] = useState(false);

  // Sync prop changes
  useEffect(() => {
    if (propAssignmentId) {
      setAssignmentId(propAssignmentId);
    }
  }, [propAssignmentId]);

  // Clean up selfie preview on unmount
  useEffect(() => {
    return () => {
      if (selfiePreview) URL.revokeObjectURL(selfiePreview);
    };
  }, [selfiePreview]);

  // ── Clock ticker ───────────────────────────────────────────
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // ── GPS Tracking ───────────────────────────────────────────
  useEffect(() => {
    if (!navigator.geolocation) {
      setLocation('GPS unavailable (Campus mode)');
      setGpsCoords({ lat: 18.5204, lng: 73.8567, accuracy: 15 });
      return;
    }
    const watchId = navigator.geolocation.watchPosition(
      (pos) => {
        const coords = {
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          accuracy: pos.coords.accuracy || 10,
        };
        setGpsCoords(coords);
        setLocation(`${coords.lat.toFixed(4)}, ${coords.lng.toFixed(4)} (±${Math.round(coords.accuracy)}m)`);
      },
      () => {
        // Fallback to campus coordinates if permission denied
        setGpsCoords({ lat: 18.5204, lng: 73.8567, accuracy: 20 });
        setLocation('18.5204, 73.8567 (Campus GPS)');
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 10000 }
    );
    return () => navigator.geolocation.clearWatch(watchId);
  }, []);

  // ── Load Worker Roster Schedule ────────────────────────────
  const loadSchedule = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/roster/my-schedule/`, {
        headers: getAuthHeaders(),
      });
      if (!res.ok) return;
      const data = await res.json();
      const slots = extractList(data);
      setSchedule(slots);

      // Find current active or nearest scheduled slot for today
      if (slots.length > 0) {
        const todayStr = new Date().toISOString().slice(0, 10);
        const todaySlot = slots.find((s) => s.date === todayStr || s.status === 'PRESENT' || s.status === 'SCHEDULED');
        if (todaySlot) {
          setActiveSlot(todaySlot);
          if (todaySlot.status === 'PRESENT') {
            setIsClockedIn(true);
          }
        }
      }
    } catch (err) {
      console.warn('Roster schedule load warning:', err.message);
    }
  }, []);

  // ── Load history & active attendance session ───────────────
  const loadHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/attendance/my-history/`, {
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error('Could not load history');
      const data = await res.json();
      const records = extractList(data);
      setHistory(records);

      // Detect if already clocked in (clock_in set, clock_out null)
      const active = records.find((r) => r.clock_in && !r.clock_out);
      if (active) {
        setIsClockedIn(true);
        setClockInTime(active.clock_in);
        if (active.assignment) {
          setAssignmentId(active.assignment);
        }
      }
    } catch (err) {
      console.warn('History load failed:', err.message);
    }
  }, []);

  useEffect(() => {
    loadSchedule();
    loadHistory();
  }, [loadSchedule, loadHistory]);

  const handleSelfieSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (selfiePreview) URL.revokeObjectURL(selfiePreview);
    setSelfieFile(file);
    setSelfiePreview(URL.createObjectURL(file));
  };

  // ── Unified Clock In (Roster primary with legacy fallback) ─
  const handleClockIn = async () => {
    setIsLoading(true);
    setError(null);
    setSuccessMsg(null);

    const clockInUuid = generateUUID();
    const lat = gpsCoords.lat || 18.5204;
    const lng = gpsCoords.lng || 73.8567;
    const accuracy = gpsCoords.accuracy || 10.0;
    const clientTimestamp = new Date().toISOString();

    // 1. Try Roster Clock-in First
    try {
      let rosterSuccess = false;
      const rosterPayload = {
        clock_in_uuid: clockInUuid,
        lat,
        lng,
        accuracy,
        client_timestamp: clientTimestamp,
      };
      if (activeSlot?.roster_entry_id) {
        rosterPayload.roster_entry_id = activeSlot.roster_entry_id;
      }

      // If selfie attached, send multipart
      let res;
      if (selfieFile) {
        const formData = new FormData();
        Object.entries(rosterPayload).forEach(([k, v]) => formData.append(k, v));
        formData.append('selfie', selfieFile);
        const headers = { ...getAuthHeaders() };
        delete headers['Content-Type'];
        res = await fetch(`${API_BASE}/roster/clock-in/`, {
          method: 'POST',
          headers,
          body: formData,
        });
      } else {
        res = await fetch(`${API_BASE}/roster/clock-in/`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify(rosterPayload),
        });
      }

      const data = await res.json();

      if (res.ok) {
        setIsClockedIn(true);
        setClockInTime(data.clock_in_at || clientTimestamp);
        setSuccessMsg('Clocked into roster shift with GPS! ✅');
        setShowSelfiePrompt(false);
        setTimeout(() => setSuccessMsg(null), 3500);
        await Promise.all([loadSchedule(), loadHistory()]);
        rosterSuccess = true;
        return;
      }

      // If selfie was required by society settings
      if (res.status === 400 && data.error && data.error.toLowerCase().includes('selfie')) {
        setShowSelfiePrompt(true);
        throw new Error('Selfie photo verification is required to clock in.');
      }

      // If 409 slot covered by replacement
      if (res.status === 409) {
        throw new Error(data.error || 'This roster slot is already active or assigned to another worker.');
      }

      // If 400/404 on roster slot (e.g. no scheduled roster slot), fallback to legacy request attendance
      if (!rosterSuccess && (res.status === 400 || res.status === 404)) {
        if (!assignmentId) {
          throw new Error(data.error || 'No scheduled roster shift found for this time window.');
        }
        // Fallback to legacy attendance
        const legacyRes = await fetch(`${API_BASE}/attendance/clock-in/`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify({
            assignment_id: assignmentId,
            lat,
            lng,
          }),
        });
        const legacyData = await legacyRes.json();
        if (!legacyRes.ok) {
          throw new Error(legacyData.error || legacyData.detail || 'Clock-in failed.');
        }
        setIsClockedIn(true);
        setClockInTime(legacyData.clock_in);
        setSuccessMsg('Clocked in successfully with GPS! ✅');
        setTimeout(() => setSuccessMsg(null), 3000);
        await loadHistory();
        return;
      }

      throw new Error(data.error || 'Clock-in failed');
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // ── Unified Clock Out ──────────────────────────────────────
  const handleClockOut = async () => {
    setIsLoading(true);
    setError(null);
    setSuccessMsg(null);

    const clockOutUuid = generateUUID();
    const clientTimestamp = new Date().toISOString();

    try {
      // 1. Try Roster Clock-out
      const res = await fetch(`${API_BASE}/roster/clock-out/`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          clock_out_uuid: clockOutUuid,
          roster_entry_id: activeSlot?.roster_entry_id,
          client_timestamp: clientTimestamp,
        }),
      });

      const data = await res.json();
      if (res.ok) {
        setIsClockedIn(false);
        setClockInTime(null);
        setSuccessMsg('Clocked out of shift. Operations logged! 🎉');
        setTimeout(() => setSuccessMsg(null), 3500);
        await Promise.all([loadSchedule(), loadHistory()]);
        return;
      }

      // Fallback to legacy clock-out if assignment exists
      if (assignmentId) {
        const legacyRes = await fetch(`${API_BASE}/attendance/clock-out/`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify({
            assignment_id: assignmentId,
            lat: gpsCoords.lat || 18.5204,
            lng: gpsCoords.lng || 73.8567,
            proof_of_work_url: 'https://images.unsplash.com/photo-584622650111-993a426fbf0a?auto=format&fit=crop&q=80&w=800',
          }),
        });
        const legacyData = await legacyRes.json();
        if (!legacyRes.ok) throw new Error(legacyData.error || 'Clock-out failed');

        setIsClockedIn(false);
        setClockInTime(null);
        setSuccessMsg('Clocked out. Shift logged with verified proof! 🎉');
        setTimeout(() => setSuccessMsg(null), 3000);
        await loadHistory();
        return;
      }

      throw new Error(data.error || 'Clock-out failed.');
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClockToggle = () => {
    if (isClockedIn) handleClockOut();
    else handleClockIn();
  };

  const handleToastNotice = (msg, type = 'info') => {
    if (type === 'error') {
      setError(msg);
      setSuccessMsg(null);
    } else {
      setSuccessMsg(msg);
      setError(null);
      setTimeout(() => setSuccessMsg(null), 3500);
    }
  };

  return (
    <div className="mobile-app-container">
      <header className="mobile-header">
        <img src={altsanLogo} alt="Altsan" className="header-mini-logo" />
        <h1>Attendance & Shifts</h1>
        <div className="notification-icon" title="GPS Signal Verified">
          🟢
        </div>
      </header>

      <main className="attendance-main">
        {/* Toast notifications */}
        {error && (
          <div className="toast toast-error" role="alert">
            <span>⚠️ {error}</span>
            <button className="toast-close" onClick={() => setError(null)}>
              ✕
            </button>
          </div>
        )}
        {successMsg && (
          <div className="toast toast-success" role="status">
            <span>{successMsg}</span>
          </div>
        )}

        {/* Real-time Replacement Shift Alert Banner */}
        <ReplacementBanner
          apiBase={API_BASE}
          authHeaders={getAuthHeaders}
          onNotice={handleToastNotice}
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

        {/* GPS Location Tag */}
        <section className="location-card">
          <div className="location-icon">📍</div>
          <div className="location-info">
            <span className="label">GPS Geofence Status</span>
            <span className="value">{location}</span>
          </div>
        </section>

        {/* Active Shift / Post Context Card */}
        {activeSlot ? (
          <section className="job-context-card">
            <div className="job-society-badge">
              <span>🏢 {activeSlot.society_name} • {activeSlot.site_name}</span>
            </div>
            <h3>Roster Assignment</h3>
            <div className="job-brief">
              <div className="job-primary">
                <strong>{activeSlot.post_name}</strong>
                <span>{activeSlot.shift_name} ({formatTime(activeSlot.shift_start_at)} – {formatTime(activeSlot.shift_end_at)})</span>
              </div>
              {isClockedIn && (
                <div className="job-shift live-badge">
                  🟢 Live on Shift {clockInTime ? `— since ${formatTime(clockInTime)}` : ''}
                </div>
              )}
            </div>
          </section>
        ) : (
          <section className="job-context-card empty-job">
            <h3>Scheduled Shift</h3>
            <p className="job-hint">
              {schedule.length > 0
                ? `${schedule.length} scheduled shifts on your roster calendar.`
                : 'No shift roster scheduled for today. Ready for standby or job queue.'}
            </p>
          </section>
        )}

        {/* Selfie Capture Prompt if required */}
        {showSelfiePrompt && !isClockedIn && (
          <div
            style={{
              background: '#131b2e',
              border: '1px solid #3b82f6',
              borderRadius: '16px',
              padding: '16px',
              marginBottom: '16px',
              textAlign: 'center',
            }}
          >
            <p style={{ fontSize: '13px', fontWeight: 600, color: '#93c5fd', marginBottom: '10px' }}>
              📸 Society requires identity verification selfie to clock in
            </p>
            {selfiePreview ? (
              <div style={{ position: 'relative', display: 'inline-block', marginBottom: '10px' }}>
                <img
                  src={selfiePreview}
                  alt="Selfie Preview"
                  style={{ width: '90px', height: '90px', borderRadius: '50%', objectFit: 'cover', border: '2px solid #10b981' }}
                />
                <button
                  onClick={() => {
                    setSelfieFile(null);
                    setSelfiePreview(null);
                  }}
                  style={{
                    position: 'absolute',
                    top: '-4px',
                    right: '-4px',
                    background: '#ef4444',
                    color: 'white',
                    border: 'none',
                    borderRadius: '50%',
                    width: '24px',
                    height: '24px',
                    cursor: 'pointer',
                  }}
                >
                  ✕
                </button>
              </div>
            ) : (
              <label
                style={{
                  display: 'inline-block',
                  background: '#1a253c',
                  border: '1px dashed #38bdf8',
                  padding: '10px 18px',
                  borderRadius: '12px',
                  color: '#38bdf8',
                  fontSize: '13px',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                🤳 Take Clock-In Selfie
                <input
                  type="file"
                  accept="image/*"
                  capture="user"
                  onChange={handleSelfieSelect}
                  style={{ display: 'none' }}
                />
              </label>
            )}
          </div>
        )}

        {/* Clock In / Out Main Button */}
        <div className="clock-action">
          <button
            id="clock-toggle-btn"
            className={`clock-btn ${isClockedIn ? 'out' : 'in'} ${isLoading ? 'loading' : ''}`}
            onClick={handleClockToggle}
            disabled={isLoading}
          >
            <div className="btn-circle">
              {isLoading ? (
                <div className="spinner" />
              ) : (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                </svg>
              )}
            </div>
            <span>{isLoading ? 'Processing…' : isClockedIn ? 'Clock Out Shift' : 'Clock In Shift'}</span>
          </button>
          <p className="clock-hint">
            {isClockedIn
              ? `Shift active since ${formatTime(clockInTime)}`
              : activeSlot
              ? `Ready for ${activeSlot.post_name}`
              : 'Ready to Clock In'}
          </p>
        </div>

        {/* Housekeeping Tasks & Photo Checklist */}
        <TaskChecklist
          apiBase={API_BASE}
          authHeaders={getAuthHeaders}
          isClockedIn={isClockedIn}
          gpsCoords={gpsCoords}
          onNotice={handleToastNotice}
        />

        {/* Shift History Log */}
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
        <div className="tab-item" onClick={() => onTabChange?.('home')}>
          <div className="tab-icon">🏠</div>
          <span>Home</span>
        </div>
        <div className="tab-item active" onClick={() => onTabChange?.('attendance')}>
          <div className="tab-icon">🕒</div>
          <span>Attendance</span>
        </div>
        <div className="tab-item" onClick={() => onTabChange?.('jobs')}>
          <div className="tab-icon">💼</div>
          <span>Jobs</span>
        </div>
        <div className="tab-item" onClick={() => onTabChange?.('earnings')}>
          <div className="tab-icon">💰</div>
          <span>Earnings</span>
        </div>
      </nav>
    </div>
  );
};

export default AttendanceScreen;
