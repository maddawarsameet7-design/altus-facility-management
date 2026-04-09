import React, { useState } from 'react';
import './JobsScreen.css';

const JobsScreen = () => {
  const [activeTab, setActiveTab] = useState('available');

  const availableJobs = [
    {
      id: "JOB-4501",
      service: "Electrical Repair",
      facility: "TechPark Tower A",
      distance: "2.4 km",
      time: "Immediate",
      pay: "$45.00"
    },
    {
      id: "JOB-4505",
      service: "Plumbing Maintenance",
      facility: "Greenwood Society",
      distance: "5.1 km",
      time: "Today, 02:00 PM",
      pay: "$38.00"
    }
  ];

  const myJobs = [
    {
      id: "JOB-4412",
      service: "Housekeeping",
      facility: "City Care Hospital",
      status: "In Progress",
      time: "08:00 AM - 04:00 PM"
    }
  ];

  return (
    <div className="mobile-app-container">
      <header className="mobile-header">
        <div className="profile-mini">MB</div>
        <h1>My Jobs</h1>
        <div className="filter-icon">🔍</div>
      </header>

      <div className="tab-switcher">
        <button 
          className={activeTab === 'available' ? 'active' : ''} 
          onClick={() => setActiveTab('available')}
        >
          Available (2)
        </button>
        <button 
          className={activeTab === 'ongoing' ? 'active' : ''} 
          onClick={() => setActiveTab('ongoing')}
        >
          Ongoing (1)
        </button>
        <button 
          className={activeTab === 'completed' ? 'active' : ''} 
          onClick={() => setActiveTab('completed')}
        >
          History
        </button>
      </div>

      <main className="jobs-main">
        {activeTab === 'available' && (
          <div className="jobs-list animate-fade-in">
            {availableJobs.map(job => (
              <div key={job.id} className="job-card available">
                <div className="job-card-header">
                  <span className="pay-badge">{job.pay}</span>
                  <span className="distance">{job.distance} away</span>
                </div>
                <h3>{job.service}</h3>
                <p className="facility-name">🏢 {job.facility}</p>
                <p className="job-time">⏰ {job.time}</p>
                <div className="job-actions">
                  <button className="btn-decline">Ignore</button>
                  <button className="btn-accept">Accept Job</button>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'ongoing' && (
          <div className="jobs-list animate-fade-in">
            {myJobs.map(job => (
              <div key={job.id} className="job-card ongoing">
                <div className="job-card-header">
                  <span className="status-tag pulse">Active Now</span>
                </div>
                <h3>{job.service}</h3>
                <p className="facility-name">🏢 {job.facility}</p>
                <p className="job-time">🕒 {job.time}</p>
                <button className="btn-full">View Job Details</button>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Reusing Tab Bar from AttendanceScreen concept */}
      <nav className="mobile-tab-bar">
        <div className="tab-item">
          <div className="tab-icon">🏠</div>
          <span>Home</span>
        </div>
        <div className="tab-item">
          <div className="tab-icon">🕒</div>
          <span>Attendance</span>
        </div>
        <div className="tab-item active">
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

export default JobsScreen;
