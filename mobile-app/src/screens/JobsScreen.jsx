import React, { useState, useEffect, useCallback } from 'react';
import altsanLogo from '../assets/altsan-logo.png';
import ReplacementBanner from '../components/ReplacementBanner.jsx';
import './JobsScreen.css';

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

const JobsScreen = ({ onTabChange, onSelectJob }) => {
  const [activeTab, setActiveTab] = useState('roster');
  const [schedule, setSchedule] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [toastMsg, setToastMsg] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);

  const fetchScheduleAndJobs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Fetch Roster Schedule
      const schedulePromise = fetch(`${API_BASE}/roster/my-schedule/`, { headers: getAuthHeaders() })
        .then((r) => (r.ok ? r.json() : []))
        .then(extractList)
        .catch(() => []);

      // 2. Fetch Service Requests / Tickets
      const requestsPromise = fetch(`${API_BASE}/requests/`, { headers: getAuthHeaders() })
        .then((r) => (r.ok ? r.json() : []))
        .then(extractList)
        .catch(() => []);

      const [scheduleData, requestsData] = await Promise.all([schedulePromise, requestsPromise]);
      setSchedule(scheduleData);
      setJobs(requestsData);
    } catch (err) {
      console.warn('Jobs & schedule fetch error:', err.message);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchScheduleAndJobs();
  }, [fetchScheduleAndJobs]);

  const handleUpdateStatus = async (jobId, newStatus) => {
    setActionLoading(jobId);
    try {
      const res = await fetch(`${API_BASE}/requests/${jobId}/update_status/`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ status: newStatus }),
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || 'Status update failed');
      }
      setToastMsg(`Status updated to ${newStatus} ✅`);
      setTimeout(() => setToastMsg(null), 3000);
      await fetchScheduleAndJobs();
    } catch (err) {
      alert(`Action error: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const ongoingJobs = jobs.filter((j) => j.status === 'In Progress' || j.status === 'Investigating');
  const availableJobs = jobs.filter((j) => j.status === 'Requested');
  const completedJobs = jobs.filter((j) => j.status === 'Resolved');

  return (
    <div className="mobile-app-container">
      <header className="mobile-header">
        <img src={altsanLogo} alt="Altsan" className="header-mini-logo" />
        <h1>Work & Assignments</h1>
        <button className="filter-icon" onClick={fetchScheduleAndJobs} title="Refresh">
          🔄
        </button>
      </header>

      {/* Replacement Offer Banner (Instant Reliever Dispatch) */}
      <ReplacementBanner
        apiBase={API_BASE}
        authHeaders={getAuthHeaders}
        onNotice={(msg, type) => {
          if (type === 'error') alert(`⚠️ ${msg}`);
          else {
            setToastMsg(msg);
            setTimeout(() => setToastMsg(null), 3500);
          }
        }}
        onScheduleUpdated={fetchScheduleAndJobs}
      />

      {toastMsg && (
        <div
          style={{
            background: 'rgba(16, 185, 129, 0.2)',
            border: '1px solid #10b981',
            color: '#86efac',
            padding: '10px 16px',
            borderRadius: '12px',
            fontSize: '13px',
            fontWeight: 600,
            marginBottom: '16px',
          }}
        >
          {toastMsg}
        </div>
      )}

      {/* Tab Switcher */}
      <div className="tab-switcher">
        <button
          className={activeTab === 'roster' ? 'active' : ''}
          onClick={() => setActiveTab('roster')}
        >
          Shifts ({schedule.length})
        </button>
        <button
          className={activeTab === 'ongoing' ? 'active' : ''}
          onClick={() => setActiveTab('ongoing')}
        >
          Tickets ({ongoingJobs.length})
        </button>
        <button
          className={activeTab === 'available' ? 'active' : ''}
          onClick={() => setActiveTab('available')}
        >
          Queue ({availableJobs.length})
        </button>
        <button
          className={activeTab === 'completed' ? 'active' : ''}
          onClick={() => setActiveTab('completed')}
        >
          Done ({completedJobs.length})
        </button>
      </div>

      <main className="jobs-main">
        {loading && (
          <div className="jobs-loading">
            <p>Syncing task board & schedule…</p>
          </div>
        )}

        {error && (
          <div className="jobs-error">
            <p>⚠️ {error}</p>
            <button onClick={fetchScheduleAndJobs}>Retry</button>
          </div>
        )}

        {/* ── Tab: Roster Shifts ──────────────────────────────── */}
        {!loading && activeTab === 'roster' && (
          <div className="jobs-list animate-fade-in">
            {schedule.length === 0 ? (
              <p className="empty-state">No scheduled shifts on your roster calendar.</p>
            ) : (
              schedule.map((slot) => (
                <div key={slot.roster_entry_id} className="job-card ongoing">
                  <div className="job-card-header">
                    <span className="status-tag pulse">
                      {slot.status === 'PRESENT' ? '🟢 Live on Shift' : slot.status}
                    </span>
                    <span className="priority-tag">{slot.date}</span>
                  </div>
                  <h3>{slot.post_name}</h3>
                  <p className="facility-name">🏢 {slot.site_name} • {slot.society_name}</p>
                  <p className="job-location">
                    🕒 {slot.shift_name} ({new Date(slot.shift_start_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} – {new Date(slot.shift_end_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })})
                  </p>

                  <div className="job-actions">
                    <button
                      className="btn-full"
                      onClick={() => onTabChange?.('attendance')}
                    >
                      🕒 Clock In & Shift Checklist
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* ── Tab: Ongoing Service Tickets ───────────────────── */}
        {!loading && activeTab === 'ongoing' && (
          <div className="jobs-list animate-fade-in">
            {ongoingJobs.length === 0 ? (
              <p className="empty-state">No service tickets currently in progress.</p>
            ) : (
              ongoingJobs.map((job) => (
                <div key={job.id} className="job-card ongoing">
                  <div className="job-card-header">
                    <span className="status-tag pulse">Active: {job.status}</span>
                    <span className="priority-tag">{job.priority || 'Normal'}</span>
                  </div>
                  <h3>{job.category?.name || 'Facility Repair'}</h3>
                  <p className="facility-name">🏢 {job.society_name || 'Altus Society'}</p>
                  <p className="job-location">📍 {job.location}</p>
                  {job.issue && <p className="job-issue">"{job.issue}"</p>}

                  <div className="job-actions">
                    <button
                      className="btn-full"
                      onClick={() => onTabChange?.('attendance', job.assignments?.[0]?.id)}
                    >
                      🕒 Attendance & Logs
                    </button>
                    {job.status !== 'Resolved' && (
                      <button
                        className="btn-resolve"
                        disabled={actionLoading === job.id}
                        onClick={() => handleUpdateStatus(job.id, 'Resolved')}
                      >
                        {actionLoading === job.id ? 'Resolving…' : '✅ Mark Completed'}
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* ── Tab: Available Ticket Queue ────────────────────── */}
        {!loading && activeTab === 'available' && (
          <div className="jobs-list animate-fade-in">
            {availableJobs.length === 0 ? (
              <p className="empty-state">No new service tickets awaiting dispatch.</p>
            ) : (
              availableJobs.map((job) => (
                <div key={job.id} className="job-card available">
                  <div className="job-card-header">
                    <span className="pay-badge">{job.priority || 'Normal'} Priority</span>
                    <span className="distance">{job.society_name || 'Society Site'}</span>
                  </div>
                  <h3>{job.category?.name || 'Service Request'}</h3>
                  <p className="facility-name">🏢 {job.society_name}</p>
                  <p className="job-location">📍 {job.location}</p>
                  {job.issue && <p className="job-issue">"{job.issue}"</p>}
                  <div className="job-actions">
                    <button
                      className="btn-accept"
                      disabled={actionLoading === job.id}
                      onClick={() => handleUpdateStatus(job.id, 'In Progress')}
                    >
                      {actionLoading === job.id ? 'Accepting…' : 'Accept Assignment'}
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* ── Tab: Completed Tickets ─────────────────────────── */}
        {!loading && activeTab === 'completed' && (
          <div className="jobs-list animate-fade-in">
            {completedJobs.length === 0 ? (
              <p className="empty-state">No completed jobs logged yet.</p>
            ) : (
              completedJobs.map((job) => (
                <div key={job.id} className="job-card completed">
                  <div className="job-card-header">
                    <span className="status-tag success">Resolved</span>
                    <span className="date">{new Date(job.created_at).toLocaleDateString()}</span>
                  </div>
                  <h3>{job.category?.name || 'Service'}</h3>
                  <p className="facility-name">🏢 {job.society_name}</p>
                  <p className="job-location">📍 {job.location}</p>
                </div>
              ))
            )}
          </div>
        )}
      </main>

      <nav className="mobile-tab-bar">
        <div className="tab-item" onClick={() => onTabChange?.('home')}>
          <div className="tab-icon">🏠</div>
          <span>Home</span>
        </div>
        <div className="tab-item" onClick={() => onTabChange?.('attendance')}>
          <div className="tab-icon">🕒</div>
          <span>Attendance</span>
        </div>
        <div className="tab-item active" onClick={() => onTabChange?.('jobs')}>
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

export default JobsScreen;
