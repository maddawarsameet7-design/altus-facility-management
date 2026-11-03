import React, { useState, useEffect, useCallback } from 'react';
import './AttendanceScreen.css';

// ── Config ─────────────────────────────────────────────────────
const API_BASE = 'http://localhost:8000/api';

const getAuthHeaders = () => ({
  'Content-Type': 'application/json',
  Authorization: `Bearer ${localStorage.getItem('access_token') || ''}`,
});

// ── Utility ────────────────────────────────────────────────────
const formatDuration = (hours) => {
  if (!hours) return '—';
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
const AttendanceScreen = ({ assignmentId, onTabChange }) => {
  const [isClockedIn, setIsClockedIn] = useState(false);
  const [clockInTime, setClockInTime] = useState(null);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [location, setLocation] = useState('Fetching location…');
  const [gpsCoords, setGpsCoords] = useState({ lat: null, lng: null });
  const [activeJob, setActiveJob] = useState(null);
  const [history, setHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // ── Clock ticker ───────────────────────────────────────────
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // ── GPS ────────────────────────────────────────────────────
  useEffect(() => {
    if (!navigator.geolocation) {
      setLocation('GPS unavailable');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGpsCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setLocation(`${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`);
      },
      () => setLocation('Location access denied'),
      { enableHighAccuracy: true }
    );
  }, []);

  // ── Load history & active record ──────────────────────────
  const loadHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/attendance/my-history/`, {
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error('Could not load history');
      const data = await res.json();
      setHistory(data);

      // Detect if already clocked in (clock_in set, clock_out null)
      const active = data.find((r) => r.clock_in && !r.clock_out);
      if (active) {
        setIsClockedIn(true);
        setClockInTime(active.clock_in);
        setActiveJob({
          id: active.assignment_id,
          service: active.service,
          location: active.location,
          society: active.society_name || 'Client Site',
        });
      }
    } catch (err) {
      // Silently fail — user may be offline
      console.warn('History load failed:', err.message);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // ── Clock In ───────────────────────────────────────────────
  const handleClockIn = async () => {
    if (!assignmentId) {
      setError('No active assignment found. Please accept a job first.');
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/attendance/clock-in/`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          assignment_id: assignmentId,
          lat: gpsCoords.lat,
          lng: gpsCoords.lng,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Clock-in failed');

      setIsClockedIn(true);
      setClockInTime(data.clock_in);
      setSuccessMsg('Clocked in successfully! ✅');
      setTimeout(() => setSuccessMsg(null), 3000);
      await loadHistory();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // ── Clock Out ──────────────────────────────────────────────
  const handleClockOut = async () => {
    if (!assignmentId) {
      setError('No active assignment found.');
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/attendance/clock-out/`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          assignment_id: assignmentId,
          lat: gpsCoords.lat,
          lng: gpsCoords.lng,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Clock-out failed');

      setIsClockedIn(false);
      setClockInTime(null);
      setSuccessMsg('Clocked out. Great work today! 🎉');
      setTimeout(() => setSuccessMsg(null), 3000);
      await loadHistory();
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

  // ── Render ─────────────────────────────────────────────────
  return (
    <div className="mobile-app-container">
      <header className="mobile-header">
        <div className="profile-mini">WK</div>
        <h1>Attendance</h1>
        <div className="notification-icon">🔔</div>
      </header>

      <main className="attendance-main">
        {/* Toast messages */}
        {error && (
          <div className="toast toast-error" role="alert">
            ⚠️ {error}
            <button className="toast-close" onClick={() => setError(null)}>✕</button>
          </div>
        )}
        {successMsg && (
          <div className="toast toast-success" role="status">
            {successMsg}
          </div>
        )}

        {/* Live Clock */}
        <div className="time-display">
          <h2>{currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</h2>
          <p>{currentTime.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })}</p>
        </div>

        {/* GPS Location */}
        <section className="location-card">
          <div className="location-icon">📍</div>
          <div className="location-info">
            <span className="label">Current Location</span>
            <span className="value">{location}</span>
          </div>
        </section>

        {/* Active Assignment */}
        {activeJob && (
          <section className="job-context-card">
            {activeJob.society && (
              <div className="job-society-badge">
                <span>🏢 {activeJob.society}</span>
              </div>
            )}
            <h3>Current Assignment</h3>
            <div className="job-brief">
              <div className="job-primary">
                <strong>{activeJob.service}</strong>
                <span>{activeJob.location}</span>
              </div>
              {isClockedIn && clockInTime && (
                <div className="job-shift live-badge">
                  🟢 Live — since {formatTime(clockInTime)}
                </div>
              )}
            </div>
          </section>
        )}

        {/* Clock Button */}
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
            <span>{isLoading ? 'Please wait…' : isClockedIn ? 'Clock Out' : 'Clock In Now'}</span>
          </button>
          <p className="clock-hint">
            {isClockedIn
              ? `Clocked in at ${formatTime(clockInTime)}`
              : 'Status: Not Clocked In'}
          </p>
        </div>

        {/* Shift History */}
        <section className="attendance-history">
          <div className="history-header">
            <h3>Recent Shifts</h3>
            <span className="shift-count">{history.length} records</span>
          </div>
          <div className="history-list">
            {history.length === 0 && (
              <p className="empty-state">No shift records yet.</p>
            )}
            {history.slice(0, 5).map((rec) => (
              <div className="history-item" key={rec.attendance_id || rec.id}>
                <div>
                  <div className="date">{formatDate(rec.clock_in)}</div>
                  {rec.society_name && (
                    <div className="history-society">🏢 {rec.society_name}</div>
                  )}
                </div>
                <div className="hours">
                  {formatTime(rec.clock_in)} – {rec.clock_out ? formatTime(rec.clock_out) : '…'}
                </div>
                <div className={`total ${!rec.clock_out ? 'active' : ''}`}>
                  {rec.clock_out ? formatDuration(rec.duration_hours) : '🟢 Active'}
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>

      <nav className="mobile-tab-bar">
        <div className="tab-item" onClick={() => onTabChange?.('home')}>
          <div className="tab-icon">🏠</div>
          <span>Home</span>
        </div>
        <div className="tab-item active">
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
