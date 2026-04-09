import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import BookingWizard from './components/BookingWizard';
import WorkerVerification from './components/WorkerVerification';
import AdminAnalytics from './components/AdminAnalytics';
import LoginRegistration from './components/LoginRegistration';
import './App.css';

const App = () => {
  return (
    <Router>
      <div className="app-main-wrapper">
        {/* Navigation Sidebar / Shortcut for Demo */}
        <nav className="demo-nav">
          <div className="nav-logo">AL</div>
          <Link to="/login">Sign In</Link>
          <Link to="/">Client Dashboard</Link>
          <Link to="/book">Book Service</Link>
          <hr style={{ opacity: 0.1, margin: '10px 0' }} />
          <Link to="/admin/verification">Worker Verification</Link>
          <Link to="/admin/analytics">Analytics</Link>
        </nav>

        <div className="app-viewport">
          <Routes>
            <Route path="/login" element={<LoginRegistration onLoginSuccess={() => window.location.href = '/'} />} />
            <Route path="/" element={<Dashboard />} />
            <Route path="/book" element={<BookingWizard />} />
            <Route path="/admin/verification" element={<WorkerVerification />} />
            <Route path="/admin/analytics" element={<AdminAnalytics />} />
          </Routes>
        </div>
      </div>
    </Router>
  );
};

export default App;
