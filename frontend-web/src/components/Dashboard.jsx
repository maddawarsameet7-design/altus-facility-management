import React, { useState } from 'react';
import TrackingMap from './TrackingMap';
import RatingModal from './RatingModal';
import './Dashboard.css';

const Dashboard = () => {
  const [activeTab, setActiveTab] = useState('upcoming');
  const [showRating, setShowRating] = useState(false);
  const [selectedBooking, setSelectedBooking] = useState(null);
  const [showWizard, setShowWizard] = useState(false);

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

  const pastBookings = [
    {
      id: "BK-9840",
      service: "Deep Cleaning",
      facility: "City Care Hospital",
      date: "Yesterday, 02:00 PM",
      workers: 2,
      status: "Completed"
    }
  ];

  const currentBookings = activeTab === 'upcoming' ? upcomingBookings : pastBookings;

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
      {/* Main Content */}
      <main className="main-content">
        <header className="top-header">
          <div>
            <h1 className="greeting">Welcome back, Sarah! 👋</h1>
            <p className="subtitle">Here is what's happening across your facilities today.</p>
          </div>
          <button className="btn-primary" onClick={() => setShowWizard(true)}>
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
                {currentBookings.map(booking => (
                  <div 
                    key={booking.id} 
                    className="booking-card" 
                    onClick={() => booking.status === 'Completed' ? handleReviewOpen(booking) : null}
                    style={{ cursor: booking.status === 'Completed' ? 'pointer' : 'default' }}
                  >
                    <div className="booking-header">
                      <span className="booking-id">{booking.id}</span>
                      <span className={`status-badge ${booking.status === 'Assigned' || booking.status === 'Completed' ? 'assigned' : 'pending'}`}>
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

      {/* Booking Wizard Modal */}
      {showWizard && (
        <div className="modal-overlay">
          <BookingWizard 
            onClose={() => setShowWizard(false)} 
            onSuccess={() => { setShowWizard(false); alert("Booking added successfully!"); }}
          />
        </div>
      )}

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
