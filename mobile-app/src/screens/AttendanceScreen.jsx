import React, { useState, useEffect } from 'react';
import './AttendanceScreen.css';

const AttendanceScreen = () => {
  const [isClockedIn, setIsClockedIn] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [location, setLocation] = useState("Fetching location...");
  const [activeJob, setActiveJob] = useState({
    id: "JOB-4412",
    facility: "City Care Hospital",
    service: "Housekeeping",
    shift: "08:00 AM - 04:00 PM"
  });

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    // Simulate location fetching
    setTimeout(() => setLocation("Block B, North Wing, Floor 2"), 2000);
    return () => clearInterval(timer);
  }, []);

  const handleClockToggle = () => {
    setIsClockedIn(!isClockedIn);
    // In a real app, this would trigger a POST to /api/attendance/clock-in/
  };

  return (
    <div className="mobile-app-container">
      <header className="mobile-header">
        <div className="profile-mini">MB</div>
        <h1>Attendance</h1>
        <div className="notification-icon">🔔</div>
      </header>

      <main className="attendance-main">
        <div className="time-display">
          <h2>{currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</h2>
          <p>{currentTime.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })}</p>
        </div>

        <section className="location-card">
          <div className="location-icon">📍</div>
          <div className="location-info">
            <span className="label">Current Location</span>
            <span className="value">{location}</span>
          </div>
        </section>

        <section className="job-context-card">
          <h3>Current Assignment</h3>
          <div className="job-brief">
            <div className="job-primary">
              <strong>{activeJob.service}</strong>
              <span>{activeJob.facility}</span>
            </div>
            <div className="job-shift">{activeJob.shift}</div>
          </div>
        </section>

        <div className="clock-action">
          <button 
            className={`clock-btn ${isClockedIn ? 'out' : 'in'}`}
            onClick={handleClockToggle}
          >
            <div className="btn-circle">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
              </svg>
            </div>
            <span>{isClockedIn ? 'Clock Out' : 'Clock In Now'}</span>
          </button>
          <p className="clock-hint">
            {isClockedIn 
              ? `You clocked in at 07:58 AM` 
              : `Status: Not Clocked In`}
          </p>
        </div>

        <section className="attendance-history">
          <div className="history-header">
            <h3>Recent Shifts</h3>
            <button className="text-btn">View All</button>
          </div>
          <div className="history-list">
            <div className="history-item">
              <div className="date">Yesterday</div>
              <div className="hours">08:00 - 16:12</div>
              <div className="total">8.2 hrs</div>
            </div>
            <div className="history-item">
              <div className="date">08 Apr</div>
              <div className="hours">07:55 - 16:05</div>
              <div className="total">8.1 hrs</div>
            </div>
          </div>
        </section>
      </main>

      <nav className="mobile-tab-bar">
        <div className="tab-item">
          <div className="tab-icon">🏠</div>
          <span>Home</span>
        </div>
        <div className="tab-item active">
          <div className="tab-icon">🕒</div>
          <span>Attendance</span>
        </div>
        <div className="tab-item">
          <div className="tab-icon">💼</div>
          <span>Jobs</span>
        </div>
        <div className="tab-item">
          <div className="tab-icon">💰</div>
          <span>Earnings</span>
        </div>
      </nav>
    </div>
  );
};

export default AttendanceScreen;
