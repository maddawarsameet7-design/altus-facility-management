import React, { useState, useEffect } from 'react';
import './WorkerPortal.css';

const WorkerPortal = ({ requests, onUpdate }) => {
  const [activeTab, setActiveTab] = useState('attendance');
  const [isClockedIn, setIsClockedIn] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());
  
  // Jobs are filtered requests that are 'Requested' or 'Open'
  const availableJobs = requests.filter(r => r.status === 'Requested');
  const activeAssignment = requests.find(r => r.status === 'In Progress' || r.status === 'Investigating');

  const handleAcceptJob = (id) => {
    if (!isClockedIn) {
      alert("Please Clock In before accepting assignments.");
      return;
    }
    onUpdate(id, 'In Progress');
  };

  const handleCompleteJob = (id) => {
    onUpdate(id, 'Resolved');
  };

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="worker-portal-container">
      <header className="portal-header">
        <div className="header-left">
          <h1>Worker Terminal</h1>
          <p className="status-indicator">
            <span className={`status-dot ${isClockedIn ? 'online' : 'offline'}`}></span>
            {isClockedIn ? 'On Duty' : 'Off Duty'}
          </p>
        </div>
        <div className="header-right">
          <div className="time-box">
            <span className="digital-clock">{currentTime.toLocaleTimeString()}</span>
          </div>
        </div>
      </header>

      <nav className="portal-tabs">
        <button className={activeTab === 'attendance' ? 'active' : ''} onClick={() => setActiveTab('attendance')}>Overview & Attendance</button>
        <button className={activeTab === 'jobs' ? 'active' : ''} onClick={() => setActiveTab('jobs')}>Job Board</button>
      </nav>

      <main className="portal-content">
        {activeTab === 'attendance' && (
          <div className="tab-pane animate-fade-in">
            <div className="attendance-layout">
              <section className="clock-card">
                <h3>Shift Management</h3>
                <div className="clock-face">
                  <div className="clock-inner">
                    <span className="timer-val">00:00:00</span>
                    <span className="timer-label">Current Shift</span>
                  </div>
                </div>
                <button 
                  className={`action-btn ${isClockedIn ? 'btn-out' : 'btn-in'}`}
                  onClick={() => setIsClockedIn(!isClockedIn)}
                >
                  {isClockedIn ? 'Clock Out' : 'Clock In Now'}
                </button>
              </section>

              <section className="assignment-card">
                <h3>Current Assignment</h3>
                {activeAssignment ? (
                  <div className="job-info-glass">
                    <div className="job-header">
                      <span className="job-tag">{activeAssignment.service}</span>
                      <span className="job-id">{activeAssignment.id}</span>
                    </div>
                    <h4>{activeAssignment.location}</h4>
                    <p>{activeAssignment.issue}</p>
                    <p className="job-time" style={{color: '#0984e3', fontWeight: 'bold'}}>Status: {activeAssignment.status}</p>
                    <button 
                      className="action-btn btn-in" 
                      style={{ marginTop: '16px', background: '#10b981' }}
                      onClick={() => handleCompleteJob(activeAssignment.id)}
                    >
                      Mark as Resolved
                    </button>
                  </div>
                ) : (
                  <div className="job-info-glass" style={{ textAlign: 'center', opacity: 0.6 }}>
                    <p>No active assignments. Check the Job Board.</p>
                  </div>
                )}
              </section>
            </div>
          </div>
        )}

        {activeTab === 'jobs' && (
          <div className="tab-pane animate-fade-in">
            <div className="jobs-grid">
              {availableJobs.map(job => (
                <div key={job.id} className="job-card-glass">
                  <div className="card-top">
                    <span className="time-tag" style={{ marginLeft: 'auto' }}>{job.time}</span>
                  </div>
                  <h3>{job.service}</h3>
                  <p className="loc">{job.location}</p>
                  <div className="card-actions">
                    <button className="btn-primary" onClick={() => handleAcceptJob(job.id)}>Accept Job</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default WorkerPortal;
