import React, { useState } from 'react';
import TrackingMap from './TrackingMap';
import RatingModal from './RatingModal';
import './Dashboard.css';

const Dashboard = () => {
  const [activeTab, setActiveTab] = useState('upcoming');
  const [showRating, setShowRating] = useState(false);
  const [selectedBooking, setSelectedBooking] = useState(null);

  const upcomingBookings = [
    {
      id: "BK-9842",
      service: "Housekeeping Team",
      facility: "City Care Hospital - Wing A",
      date: "Tomorrow, 08:00 AM",
      workers: 4,
      status: "Assigned"
    },
    {
      id: "BK-9843",
      service: "Electrical Maintenance",
      facility: "TechPark Corporate Office",
      date: "Oct 12, 10:00 AM",
      workers: 1,
      status: "Pending Accept"
    }
  ];

  const handleReviewOpen = (booking) => {
    setSelectedBooking(booking);
    setShowRating(true);
  };

  const handleReviewSubmit = (reviewData) => {
    console.log("DEBUG: Review Submitted", reviewData);
    setShowRating(false);
  };

  return (
    <div className="dashboard-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">AL</div>
          <h2>Altus</h2>
        </div>
        
        <nav className="nav-menu">
          <a href="#" className="nav-item active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
            Dashboard
          </a>
          <a href="#" className="nav-item">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path></svg>
            My Bookings
          </a>
          <a href="#" className="nav-item">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path></svg>
            Properties
          </a>
          <a href="#" className="nav-item">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
            Invoices
          </a>
          <a href="#" className="nav-item">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
            Settings
          </a>
        </nav>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <header className="top-header">
          <div>
            <h1 className="greeting">Welcome back, Sarah! 👋</h1>
            <p className="subtitle">Here is what's happening across your facilities today.</p>
          </div>
          <button className="btn-primary">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
            New Booking
          </button>
        </header>

        <div className="dashboard-grid-layout">
          <div className="left-panel">
            {/* Stats Row */}
            <section className="stats-grid">
              <div className="stat-card">
                <div className="stat-icon blue">⚡</div>
                <div className="stat-info">
                  <h3>Active Jobs</h3>
                  <p className="stat-value">12</p>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-icon green">✔️</div>
                <div className="stat-info">
                  <h3>Completed</h3>
                  <p className="stat-value">48</p>
                </div>
              </div>
            </section>

            {/* Bookings Area */}
            <section className="bookings-section">
              <div className="section-header">
                <h2>Service Requests</h2>
                <div className="tab-group">
                  <button 
                    className={`tab ${activeTab === 'upcoming' ? 'active' : ''}`}
                    onClick={() => setActiveTab('upcoming')}
                  >Upcoming</button>
                  <button 
                    className={`tab ${activeTab === 'past' ? 'active' : ''}`}
                    onClick={() => setActiveTab('past')}
                  >Past</button>
                </div>
              </div>

              <div className="booking-list">
                {upcomingBookings.map(booking => (
                  <div key={booking.id} className="booking-card" onClick={() => handleReviewOpen(booking)}>
                    <div className="booking-header">
                      <span className="booking-id">{booking.id}</span>
                      <span className={`status-badge ${booking.status === 'Assigned' ? 'assigned' : 'pending'}`}>
                        {booking.status}
                      </span>
                    </div>
                    <h3 className="service-title">{booking.service}</h3>
                    <div className="booking-details">
                      <div className="detail-item">📍 {booking.facility}</div>
                      <div className="detail-item">📅 {booking.date}</div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>

          <div className="right-panel">
            {/* Real-time Tracking Map */}
            <TrackingMap />
            
            <div className="promotion-card">
                <h3>Altus Premium</h3>
                <p>Unlock priority dispatch and 24/7 account management.</p>
                <button className="btn-secondary">Learn More</button>
            </div>
          </div>
        </div>
      </main>

      {/* Review Modal */}
      {showRating && (
        <RatingModal 
          booking={selectedBooking} 
          workerName="Rajesh K."
          onClose={() => setShowRating(false)}
          onSubmit={handleReviewSubmit}
        />
      )}
    </div>
  );
};

export default Dashboard;
