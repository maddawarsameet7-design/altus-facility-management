import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Power, MapPin, Clock, CheckCircle2, ChevronRight, Activity, AlertCircle } from 'lucide-react';
import './WorkerPortal.css';

const WorkerPortal = ({ requests, onUpdate }) => {
  const [activeTab, setActiveTab] = useState('attendance');
  const [isClockedIn, setIsClockedIn] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());
  
  const availableJobs = requests.filter(r => r.status === 'Requested');
  const activeAssignment = requests.find(r => r.status === 'In Progress' || r.status === 'Investigating');

  const handleAcceptJob = (id) => {
    if (!isClockedIn) {
      alert("Please Clock In before accepting assignments.");
      return;
    }
    onUpdate(id, 'In Progress');
    setActiveTab('attendance'); // Redirect to current assignment
  };

  const handleCompleteJob = (id) => {
    onUpdate(id, 'Resolved');
  };

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const cardVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.4 } }
  };

  return (
    <div className="worker-portal-container">
      <header className="terminal-header">
        <div className="t-header-top">
          <div>
            <h1>Field Terminal</h1>
            <p className="terminal-subtitle">Altsan Operations Network</p>
          </div>
          <div className="t-clock-display">
            {currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </div>
        </div>
        
        <div className="t-nav-tabs">
          <button 
            className={`t-tab ${activeTab === 'attendance' ? 'active' : ''}`} 
            onClick={() => setActiveTab('attendance')}
          >
            Dashboard
          </button>
          <button 
            className={`t-tab ${activeTab === 'jobs' ? 'active' : ''}`} 
            onClick={() => setActiveTab('jobs')}
          >
            Job Board
            {availableJobs.length > 0 && <span className="job-badge">{availableJobs.length}</span>}
          </button>
        </div>
      </header>

      <main className="terminal-main">
        <AnimatePresence mode="wait">
          {activeTab === 'attendance' && (
            <motion.div 
              key="attendance"
              initial="hidden"
              animate="visible"
              exit={{ opacity: 0, y: -20 }}
              variants={cardVariants}
              className="t-pane"
            >
              {/* Massive Clock In Button Section */}
              <div className="clock-section">
                <div className="clock-status-ring">
                  <motion.button 
                    whileTap={{ scale: 0.95 }}
                    className={`power-btn ${isClockedIn ? 'on' : 'off'}`}
                    onClick={() => setIsClockedIn(!isClockedIn)}
                  >
                    <Power size={48} />
                  </motion.button>
                </div>
                <div className="clock-status-text">
                  <h2 style={{ color: isClockedIn ? '#10B981' : '#6B7280' }}>
                    {isClockedIn ? 'SYSTEM ACTIVE' : 'SYSTEM STANDBY'}
                  </h2>
                  <p>{isClockedIn ? 'You are currently on duty.' : 'Tap the core to clock in.'}</p>
                </div>
              </div>

              {/* Current Assignment Card */}
              <div className="current-mission">
                <div className="mission-header">
                  <Activity size={18} className="mission-icon" />
                  <h3>Current Mission</h3>
                </div>
                
                {activeAssignment ? (
                  <div className="mission-card">
                    <div className="m-card-top">
                      <span className="m-id">ID: {activeAssignment.id}</span>
                      <span className="m-status pulse">{activeAssignment.status}</span>
                    </div>
                    <div className="m-details">
                      <h4>{activeAssignment.service}</h4>
                      <p className="m-loc"><MapPin size={14} /> {activeAssignment.location}</p>
                      <div className="m-issue">
                        <AlertCircle size={14} />
                        <p>{activeAssignment.issue}</p>
                      </div>
                    </div>
                    <button 
                      className="m-complete-btn"
                      onClick={() => handleCompleteJob(activeAssignment.id)}
                    >
                      <CheckCircle2 size={20} /> Mark Mission Complete
                    </button>
                  </div>
                ) : (
                  <div className="empty-mission">
                    <CheckCircle2 size={32} style={{ opacity: 0.3 }} />
                    <p>No active missions.</p>
                    {isClockedIn && (
                      <button className="t-text-btn" onClick={() => setActiveTab('jobs')}>
                        Check Job Board <ChevronRight size={16} />
                      </button>
                    )}
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {activeTab === 'jobs' && (
            <motion.div 
              key="jobs"
              initial="hidden"
              animate="visible"
              exit={{ opacity: 0, y: -20 }}
              className="t-pane jobs-grid"
            >
              {availableJobs.length === 0 ? (
                <div className="empty-mission" style={{ marginTop: '40px' }}>
                  <p>No open jobs available on the network.</p>
                </div>
              ) : (
                availableJobs.map((job, idx) => (
                  <motion.div 
                    key={job.id} 
                    variants={cardVariants}
                    initial="hidden"
                    animate="visible"
                    transition={{ delay: idx * 0.1 }}
                    className="dispatch-ticket"
                  >
                    <div className="ticket-edge" />
                    <div className="ticket-content">
                      <div className="t-meta">
                        <span className="t-id">{job.id}</span>
                        <span className="t-time"><Clock size={12}/> {job.time}</span>
                      </div>
                      <h3>{job.service}</h3>
                      <p className="t-loc"><MapPin size={14} /> {job.location}</p>
                      <button 
                        className="t-accept-btn" 
                        onClick={() => handleAcceptJob(job.id)}
                      >
                        Accept Mission
                      </button>
                    </div>
                  </motion.div>
                ))
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
};

export default WorkerPortal;
