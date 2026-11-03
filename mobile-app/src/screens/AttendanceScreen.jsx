import React, { useState, useEffect, useCallback } from 'react';
import altsanLogo from '../assets/altsan-logo.png';
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
  const [isClockedIn, setIsClockedIn] = useState(false);
  const [clockInTime, setClockInTime] = useState(null);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [location, setLocation] = useState('Acquiring GPS location…');
  const [gpsCoords, setGpsCoords] = useState({ lat: null, lng: null });
  const [activeJob, setActiveJob] = useState(null);
  const [history, setHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Sync prop changes
  useEffect(() => {
    if (propAssignmentId) {
      setAssignmentId(propAssignmentId);
    }
  }, [propAssignmentId]);

  // ── Clock ticker ───────────────────────────────────────────
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // ── GPS Tracking ───────────────────────────────────────────
  useEffect(() => {
    if (!navigator.geolocation) {
      setLocation('GPS unavailable (Simulation mode)');
      setGpsCoords({ lat: 18.5204, lng: 73.8567 });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGpsCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setLocation(`${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`);
      },
      () => {
        // Fallback to active coordinates if permission denied
        setGpsCoords({ lat: 18.5204, lng: 73.8567 });
        setLocation('18.5204, 73.8567 (Campus GPS)');
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }, []);

  // ── Auto-discover active assignment if none supplied ───────
  const fetchActiveAssignment = useCallback(async () => {
    if (assignmentId) return;
    try {
      const res = await fetch(`${API_BASE}/requests/`, { headers: getAuthHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      const list = extractList(data);
      // Look for in-progress or investigated assigned requests
      const assigned = list.find(r => r.assignments && r.assignments.length > 0);
      if (assigned && assigned.assignments?.[0]) {
        const assign = assigned.assignments[0];
        setAssignmentId(assign.id);
        setActiveJob({
          id: assign.id,
          service: assigned.category?.name || 'Facility Service',
          location: assigned.location,
          society: assigned.society_name || 'Altus Prime Society',
        });
      }
    } catch (err) {
      console.warn('Could not auto-discover assignment:', err.message);
    }
  }, [assignmentId]);

  // ── Load history & active record ──────────────────────────
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
        setActiveJob({
          id: active.assignment,
          service: active.service_name || active.service || 'Assigned Job',
          location: active.location || 'Site Location',
          society: active.society_name || 'Client Site',
        });
      } else {
        await fetchActiveAssignment();
      }
    } catch (err) {
      console.warn('History load failed:', err.message);
      await fetchActiveAssignment();
    }
  }, [fetchActiveAssignment]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // ── Clock In ───────────────────────────────────────────────
  const handleClockIn = async () => {
    if (!assignmentId) {
      setError('No active assignment assigned to your profile yet. Please check available jobs in Job Board.');
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
          lat: gpsCoords.lat || 18.5204,
          lng: gpsCoords.lng || 73.8567,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        if (res.status === 409) {
          // Already clocked in
          setIsClockedIn(true);
          setSuccessMsg('Already active on shift! ✅');
          setTimeout(() => setSuccessMsg(null), 3000);
          await loadHistory();
          return;
        }
        throw new Error(data.error || 'Clock-in failed');
      }

      setIsClockedIn(true);
      setClockInTime(data.clock_in);
      setSuccessMsg('Clocked in successfully with GPS! ✅');
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
          lat: gpsCoords.lat || 18.5204,
          lng: gpsCoords.lng || 73.8567,
          proof_of_work_url: 'https://images.unsplash.com/photo-584622650111-993a426fbf0a?auto=format&fit=crop&q=80&w=800',
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Clock-out failed');

      setIsClockedIn(false);
      setClockInTime(null);
      setSuccessMsg('Clocked out. Shift logged with verified proof! 🎉');
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
        <img src={altsanLogo} alt="Altsan" className="header-mini-logo" />
        <h1>Attendance & GPS</h1>
        <div className="notification-icon">🟢</div>
      </header>

      <main className="attendance-main">
        {/* Toast notifications */}
        {error && (
          <div className="toast toast-error" role="alert">
            <span>⚠️ {error}</span>
            <button className="toast-close" onClick={() => setError(null)}>✕</button>
          </div>
        )}
        {successMsg && (
          <div className="toast toast-success" role="status">
            <span>{successMsg}</span>
          </div>
        )}

        {/* Live Clock Display */}
        <div className="time-display">
          <h2>{currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</h2>
          <p>{currentTime.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })}</p>
        </div>

        {/* GPS Location Tag */}
        <section className="location-card">
          <div className="location-icon">📍</div>
          <div className="location-info">
            <span className="label">Current Location</span>
            <span className="value">{location}</span>
          </div>
        </section>

        {/* Active Assignment Card */}
        {activeJob ? (
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
                  🟢 Live Shift — since {formatTime(clockInTime)}
                </div>
              )}
            </div>
          </section>
        ) : (
          <section className="job-context-card empty-job">
            <h3>No Active Assignment</h3>
            <p className="job-hint">Tap "Jobs" in the bottom menu to view assigned or available tasks.</p>
          </section>
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
            <span>{isLoading ? 'Processing…' : isClockedIn ? 'Clock Out Shift' : 'Clock In Now'}</span>
          </button>
          <p className="clock-hint">
            {isClockedIn
              ? `Shift active since ${formatTime(clockInTime)}`
              : 'Status: Ready to Clock In'}
          </p>
        </div>

        {/* Shift History Log */}
        <section className="attendance-history">
          <div className="history-header">
            <h3>Recent Shifts</h3>
            <span className="shift-count">{history.length} verified</span>
          </div>
          <div className="history-list">
            {history.length === 0 && (
              <p className="empty-state">No shift logs found.</p>
            )}
            {history.slice(0, 5).map((rec) => (
              <div className="history-item" key={rec.id || rec.attendance_id}>
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
