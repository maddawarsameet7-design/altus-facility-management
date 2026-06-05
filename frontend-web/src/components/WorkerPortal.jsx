import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Power, MapPin, Clock, CheckCircle2, ChevronRight, Activity, 
  AlertCircle, Wifi, QrCode, Camera, UploadCloud, X, Wallet, TrendingUp,
  Map, Fingerprint
} from 'lucide-react';
import './WorkerPortal.css';

const WorkerPortal = ({ requests, onUpdate }) => {
  const [activeTab, setActiveTab] = useState('attendance');
  const [isClockedIn, setIsClockedIn] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [shiftStart, setShiftStart] = useState(null);
  
  // New State for Photo Proof
  const [showProofUpload, setShowProofUpload] = useState(false);
  const [proofFile, setProofFile] = useState(null);
  const fileInputRef = useRef(null);

  const availableJobs = requests.filter(r => r.status === 'Requested');
  const activeAssignment = requests.find(r => r.status === 'In Progress' || r.status === 'Investigating');

  const handleClockToggle = () => {
    if (isClockedIn) {
      setIsClockedIn(false);
      setShiftStart(null);
    } else {
      setIsVerifying(true);
      setTimeout(() => {
        setIsVerifying(false);
        setIsClockedIn(true);
        setShiftStart(new Date());
      }, 2500);
    }
  };

  const handleAcceptJob = (id) => {
    if (!isClockedIn) {
      alert("Please Clock In before accepting assignments.");
      return;
    }
    onUpdate(id, 'In Progress');
    setActiveTab('attendance'); 
  };

  const handleInitiateCompletion = () => {
    setShowProofUpload(true);
  };

  const handleFinalizeCompletion = (id) => {
    onUpdate(id, 'Resolved');
    setShowProofUpload(false);
    setProofFile(null);
  };

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const getShiftDuration = () => {
    if (!shiftStart) return "00:00:00";
    const diff = Math.floor((currentTime - shiftStart) / 1000);
    const h = String(Math.floor(diff / 3600)).padStart(2, '0');
    const m = String(Math.floor((diff % 3600) / 60)).padStart(2, '0');
    const s = String(diff % 60).padStart(2, '0');
    return `${h}:${m}:${s}`;
  };

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
            <div className="network-status">
               <Wifi size={12} className="pulse-wifi" />
               <span>Altsan Secure Sync: Active</span>
            </div>
          </div>
          <div className="t-clock-display">
            {currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </div>
        </div>
        
        <div className="t-nav-tabs">
          <button className={`t-tab ${activeTab === 'attendance' ? 'active' : ''}`} onClick={() => setActiveTab('attendance')}>
            Dashboard
          </button>
          <button className={`t-tab ${activeTab === 'jobs' ? 'active' : ''}`} onClick={() => setActiveTab('jobs')}>
            Job Board
            {availableJobs.length > 0 && <span className="job-badge">{availableJobs.length}</span>}
          </button>
          <button className={`t-tab ${activeTab === 'earnings' ? 'active' : ''}`} onClick={() => setActiveTab('earnings')}>
            Shift & Payout
          </button>
        </div>
      </header>

      <main className="terminal-main">
        <AnimatePresence mode="wait">
          {activeTab === 'attendance' && (
            <motion.div key="attendance" initial="hidden" animate="visible" exit={{ opacity: 0, y: -20 }} variants={cardVariants} className="t-pane">
              
              <div className="clock-section">
                <div className="clock-status-ring">
                  <motion.button 
                    whileTap={!isVerifying ? { scale: 0.95 } : {}}
                    className={`power-btn ${isClockedIn ? 'on' : 'off'} ${isVerifying ? 'verifying' : ''}`}
                    onClick={handleClockToggle}
                    disabled={isVerifying}
                  >
                    {isVerifying ? <Fingerprint size={48} className="scanning-icon" /> : <Power size={48} />}
                  </motion.button>
                </div>
                <div className="clock-status-text">
                  <h2 style={{ color: isVerifying ? '#3b82f6' : isClockedIn ? '#10B981' : '#6B7280' }}>
                    {isVerifying ? 'VERIFYING GPS...' : isClockedIn ? 'SYSTEM ACTIVE' : 'SYSTEM STANDBY'}
                  </h2>
                  <p>
                    {isVerifying ? 'Locating device in geofence...' : 
                     isClockedIn ? `Shift Duration: ${getShiftDuration()}` : 
                     'Tap the core to clock in.'}
                  </p>
                </div>
              </div>

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

                    {!showProofUpload ? (
                      <div className="mission-actions">
                        <button className="m-scan-btn">
                          <QrCode size={18} /> Scan Location
                        </button>
                        <button className="m-complete-btn" onClick={handleInitiateCompletion}>
                          <CheckCircle2 size={18} /> Complete Job
                        </button>
                      </div>
                    ) : (
                      <div className="proof-upload-section">
                        <h4>Photo Proof Required</h4>
                        <p>Please upload a photo of the completed work before finalizing.</p>
                        
                        <div className={`proof-dropzone ${proofFile ? 'has-file' : ''}`} onClick={() => fileInputRef.current?.click()}>
                           <input 
                              type="file" accept="image/*" className="hidden-file-input" ref={fileInputRef}
                              onChange={(e) => { if (e.target.files[0]) setProofFile(e.target.files[0]); }}
                           />
                           {proofFile ? (
                             <div className="proof-file">
                                <Camera size={20} className="text-emerald" />
                                <span>{proofFile.name}</span>
                                <X size={16} onClick={(e) => { e.stopPropagation(); setProofFile(null); }} className="close-icon" />
                             </div>
                           ) : (
                             <div className="proof-prompt">
                                <UploadCloud size={24} /> Tap to Capture / Upload Photo
                             </div>
                           )}
                        </div>
                        
                        <div className="proof-actions">
                          <button className="m-scan-btn" onClick={() => setShowProofUpload(false)}>Cancel</button>
                          <button 
                            className="m-complete-btn" 
                            disabled={!proofFile}
                            onClick={() => handleFinalizeCompletion(activeAssignment.id)}
                            style={{ opacity: !proofFile ? 0.5 : 1 }}
                          >
                            Finalize & Submit
                          </button>
                        </div>
                      </div>
                    )}
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
            <motion.div key="jobs" initial="hidden" animate="visible" exit={{ opacity: 0, y: -20 }} className="t-pane jobs-grid">
              {availableJobs.length === 0 ? (
                <div className="empty-mission" style={{ marginTop: '40px' }}>
                  <p>No open jobs available on the network.</p>
                </div>
              ) : (
                availableJobs.map((job, idx) => (
                  <motion.div key={job.id} variants={cardVariants} initial="hidden" animate="visible" transition={{ delay: idx * 0.1 }} className="dispatch-ticket">
                    <div className="ticket-edge" />
                    <div className="ticket-content">
                      <div className="t-meta">
                        <span className="t-id">{job.id}</span>
                        <span className="t-time"><Clock size={12}/> {job.time}</span>
                      </div>
                      <h3>{job.service}</h3>
                      <p className="t-loc"><MapPin size={14} /> {job.location}</p>
                      <button className="t-accept-btn" onClick={() => handleAcceptJob(job.id)}>
                        Accept Mission
                      </button>
                    </div>
                  </motion.div>
                ))
              )}
            </motion.div>
          )}

          {activeTab === 'earnings' && (
            <motion.div key="earnings" initial="hidden" animate="visible" exit={{ opacity: 0, y: -20 }} className="t-pane">
               <div className="earnings-summary">
                  <div className="e-card main">
                     <Wallet size={24} className="e-icon" />
                     <span className="balance-label">Available Balance</span>
                     <h2>₹48,550.00</h2>
                  </div>
                  <div className="e-card side">
                     <TrendingUp size={20} className="e-icon text-emerald" />
                     <span>Jobs Done</span>
                     <h3>12</h3>
                  </div>
               </div>

               <div className="shift-history">
                  <div className="mission-header">
                     <Clock size={18} className="mission-icon" />
                     <h3>Recent Shifts</h3>
                  </div>
                  
                  {[
                     { day: 'Today', hours: '6.5 hrs', earned: '₹1,300.00', status: 'Pending' },
                     { day: 'Yesterday', hours: '8.0 hrs', earned: '₹1,600.00', status: 'Paid' },
                     { day: 'Mon, Oct 12', hours: '7.2 hrs', earned: '₹1,440.00', status: 'Paid' }
                  ].map((shift, idx) => (
                     <div key={idx} className="shift-row">
                        <div className="s-left">
                           <strong>{shift.day}</strong>
                           <span>{shift.hours} logged</span>
                        </div>
                        <div className="s-right">
                           <strong>{shift.earned}</strong>
                           <span className={`s-status ${shift.status.toLowerCase()}`}>{shift.status}</span>
                        </div>
                     </div>
                  ))}
               </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
};

export default WorkerPortal;
