import React, { useState, useEffect, useCallback } from 'react';
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
  const [activeTab, setActiveTab] = useState('ongoing');
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/requests/`, { headers: getAuthHeaders() });
      if (!res.ok) throw new Error(`Could not load jobs (HTTP ${res.status})`);
      const data = await res.json();
      setJobs(extractList(data));
    } catch (err) {
      console.warn('Job fetch error:', err.message);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

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
      await fetchJobs();
    } catch (err) {
      alert(`Action error: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const ongoingJobs = jobs.filter(j => j.status === 'In Progress' || j.status === 'Investigating');
  const availableJobs = jobs.filter(j => j.status === 'Requested');
  const completedJobs = jobs.filter(j => j.status === 'Resolved');

  return (
    <div className="mobile-app-container">
      <header className="mobile-header">
        <div className="profile-mini">WK</div>
        <h1>My Tasks & Jobs</h1>
        <button className="filter-icon" onClick={fetchJobs} title="Refresh">🔄</button>
      </header>

      <div className="tab-switcher">
        <button 
          className={activeTab === 'ongoing' ? 'active' : ''} 
          onClick={() => setActiveTab('ongoing')}
        >
          Active ({ongoingJobs.length})
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
          Completed ({completedJobs.length})
        </button>
      </div>

      <main className="jobs-main">
        {loading && (
          <div className="jobs-loading">
            <p>Syncing task board…</p>
          </div>
        )}

        {error && (
          <div className="jobs-error">
            <p>⚠️ {error}</p>
            <button onClick={fetchJobs}>Retry</button>
          </div>
        )}

        {!loading && activeTab === 'ongoing' && (
          <div className="jobs-list animate-fade-in">
            {ongoingJobs.length === 0 ? (
              <p className="empty-state">No jobs currently in progress.</p>
            ) : (
              ongoingJobs.map(job => (
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
                      🕒 Clock & Attendance
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

        {!loading && activeTab === 'available' && (
          <div className="jobs-list animate-fade-in">
            {availableJobs.length === 0 ? (
              <p className="empty-state">No new jobs awaiting dispatch.</p>
            ) : (
              availableJobs.map(job => (
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

        {!loading && activeTab === 'completed' && (
          <div className="jobs-list animate-fade-in">
            {completedJobs.length === 0 ? (
              <p className="empty-state">No completed jobs logged yet.</p>
            ) : (
              completedJobs.map(job => (
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
