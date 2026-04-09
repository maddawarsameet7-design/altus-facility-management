import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import BookingWizard from './components/BookingWizard';
import WorkerVerification from './components/WorkerVerification';
import AdminAnalytics from './components/AdminAnalytics';
import LoginRegistration from './components/LoginRegistration';
import './App.css';

const SidebarLink = ({ to, children, icon }) => {
  const location = useLocation();
  const isActive = location.pathname === to;
  return (
    <Link to={to} className={`nav-item ${isActive ? 'active' : ''}`}>
      {icon}
      {children}
    </Link>
  );
};

const App = () => {
  return (
    <Router>
      <div className="app-main-wrapper">
        <aside className="main-sidebar">
          <div className="brand">
            <div className="brand-logo">AL</div>
            <h1 className="brand-name">Altus</h1>
          </div>
          
          <nav className="nav-menu">
            <SidebarLink to="/" icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>}>
              Dashboard
            </SidebarLink>
            <SidebarLink to="/book" icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path></svg>}>
              Book Service
            </SidebarLink>
            <div className="nav-divider">Admin Portal</div>
            <SidebarLink to="/admin/verification" icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>}>
              Verification
            </SidebarLink>
            <SidebarLink to="/admin/analytics" icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>}>
              Analytics
            </SidebarLink>
            <div className="nav-spacer"></div>
            <SidebarLink to="/login" icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"></path><polyline points="10 17 15 12 10 7"></polyline><line x1="15" y1="12" x2="3" y2="12"></line></svg>}>
              Sign Out
            </SidebarLink>
          </nav>
        </aside>

        <main className="app-viewport">
          <Routes>
            <Route path="/login" element={<LoginRegistration onLoginSuccess={() => window.location.href = '/'} />} />
            <Route path="/" element={<Dashboard />} />
            <Route path="/book" element={<BookingWizard />} />
            <Route path="/admin/verification" element={<WorkerVerification />} />
            <Route path="/admin/analytics" element={<AdminAnalytics />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
};

export default App;
