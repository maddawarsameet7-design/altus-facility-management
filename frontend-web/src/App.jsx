import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import { requestApi, reviewApi } from './utils/api';
import useStore from './store/useStore';
import { 
  Home,
  Briefcase,
  UserCircle,
  BarChart3,
  LogOut,
  PlusCircle,
  FileText,
  Zap,
  Droplets,
  Trash2,
  Shield,
  Sparkles
} from 'lucide-react';

import Dashboard from './components/Dashboard';
import MemberTickets from './components/MemberTickets';
import BookingWizard from './components/BookingWizard';
import WorkerVerification from './components/WorkerVerification';
import AdminAnalytics from './components/AdminAnalytics';
import LoginRegistration from './components/LoginRegistration';
import WorkerPortal from './components/WorkerPortal';
import SupervisorConsole from './components/SupervisorConsole';
import DirectorPortal from './components/DirectorPortal';
import ReviewModal from './components/ReviewModal';
import ChatWindow from './components/ChatWindow';
import PaymentCheckout from './components/PaymentCheckout';
import TrackingMap from './components/TrackingMap';
import NotificationCenter from './components/NotificationCenter';
import ProductTour from './components/ProductTour';
import { ThemeProvider, useTheme } from './context/ThemeContext';
import { Bell, Sun, Moon } from 'lucide-react';
import './App.css';

// New Mobile-First Floating Pill Navigation Item
const BottomNavLink = ({ to, icon: Icon, onClick }) => {
  const location = useLocation();
  const isActive = location.pathname === to;
  
  if (onClick) {
    return (
      <button onClick={onClick} className={`bottom-nav-item ${isActive ? 'active' : ''}`}>
        <Icon size={22} strokeWidth={isActive ? 2.5 : 2} />
      </button>
    );
  }

  return (
    <Link to={to} className={`bottom-nav-item ${isActive ? 'active' : ''}`}>
      <Icon size={22} strokeWidth={isActive ? 2.5 : 2} />
      {isActive && <div className="nav-active-dot" />}
    </Link>
  );
};

const getIconForCategory = (name) => {
  const map = {
    'Housekeeping': { icon: Sparkles, color: 'var(--accent-green)' },
    'Security Guard': { icon: Shield, color: 'var(--accent-blue)' },
    'Electrician': { icon: Zap, color: 'var(--accent-orange)' },
    'Plumber': { icon: Droplets, color: 'var(--accent-blue)' },
    'Gardening': { icon: Sparkles, color: 'var(--accent-green)' }
  };
  return map[name] || { icon: FileText, color: '#666' };
};

const MainLayout = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('altsan_token'));
  const [currentRole, setCurrentRole] = useState(localStorage.getItem('altsan_role') || 'member');
  const [currentUser, setCurrentUser] = useState(localStorage.getItem('altsan_user') || null);
  const navigate = useNavigate();

  // Consume Global State
  const { requests: globalRequests, setRequests } = useStore();

  const [showReviewFor, setShowReviewFor] = useState(null);
  const [activeChat, setActiveChat] = useState(null);
  const [activeCheckout, setActiveCheckout] = useState(null);
  const [showNotifications, setShowNotifications] = useState(false);
  const { isDark, toggleTheme } = useTheme();

  const fetchRequests = useCallback(async () => {
    try {
      console.log("Fetching service requests...");
      const response = await requestApi.getAll();
      
      if (!Array.isArray(response.data)) {
        console.warn("API returned non-array data:", response.data);
        return;
      }

      const mapped = response.data.map(req => {
        const catName = req.category?.name || 'Unknown';
        const style = getIconForCategory(catName);
        
        let progress = 0;
        if (req.status === 'Investigating') progress = 30;
        else if (req.status === 'In Progress') progress = 60;
        else if (req.status === 'Resolved') progress = 100;

        // Extract primary worker from assignments
        const primaryAssignment = req.assignments?.find(a => a.status === 'ACCEPTED') || req.assignments?.[0];
        const assignedWorker = primaryAssignment ? {
          id: primaryAssignment.worker.id,
          name: primaryAssignment.worker.user.username,
          phone: primaryAssignment.worker.phone,
          rating: primaryAssignment.worker.average_rating || 4.5,
          location: { lat: primaryAssignment.worker.current_lat, lng: primaryAssignment.worker.current_lng }
        } : null;

        return {
          ...req,
          service: catName,
          reporter: req.reporter?.username || 'System',
          time: 'Active',
          icon: style.icon,
          color: style.color,
          progress: progress,
          cost: req.total_amount ? `₹${req.total_amount}` : 'Pending',
          worker: assignedWorker
        };
      });
      
      setRequests(mapped);
    } catch (err) {
      console.error("API Fetch Error:", err);
    }
  }, [setRequests]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchRequests();
      const interval = setInterval(fetchRequests, 10000);
      return () => clearInterval(interval);
    }
  }, [isAuthenticated, fetchRequests]);

  const updateRequestStatus = async (id, newStatus) => {
    try {
      await requestApi.updateStatus(id, newStatus);
      fetchRequests();
    } catch (err) {
      console.error("Status Update Failed:", err);
    }
  };

  const handleBookingSuccess = async (serviceData) => {
    try {
      await requestApi.create({
        category_id: serviceData.id,
        location: "Resident Block A",
        issue: "Standard facility request from mobile",
        priority: "Normal"
      });
      fetchRequests();
      navigate('/');
    } catch (err) {
      console.error("Booking Error:", err);
      alert("Failed to create booking: " + (err.response?.data?.error || err.message));
    }
  };

  const handleLoginSuccess = (payload) => {
    // Normalize role to lowercase for consistent UI logic
    const normalizedRole = payload.role.toLowerCase();
    
    setIsAuthenticated(true);
    setCurrentRole(normalizedRole);
    setCurrentUser(payload.username);
    
    localStorage.setItem('altsan_role', normalizedRole);
    localStorage.setItem('altsan_user', payload.username);
    
    if (normalizedRole === 'worker') navigate('/worker');
    else if (normalizedRole === 'supervisor') navigate('/supervisor');
    else if (normalizedRole === 'director') navigate('/director');
    else navigate('/');
  };

  const handleReviewSubmit = async (reviewData) => {
    try {
      await reviewApi.create(reviewData);
      setShowReviewFor(null);
      fetchRequests();
    } catch (err) {
      console.error("Review Submission Error:", err);
    }
  };

  const handleSignOut = (e) => {
    if(e) e.preventDefault();
    localStorage.clear();
    setIsAuthenticated(false);
    setCurrentRole('member');
    setCurrentUser(null);
    navigate('/login');
  };

  const handleSendMessage = async (content) => {
    if (!activeChat) return;
    try {
      await requestApi.sendMessage(activeChat.id, content);
      fetchRequests(); // Refresh to see the new message
    } catch (err) {
      console.error("Message Error:", err);
    }
  };

  const handlePaymentSuccess = async (txData) => {
    if (!activeCheckout) return;
    try {
      await requestApi.processPayment(activeCheckout.id, txData.amount);
      setActiveCheckout(null);
      fetchRequests();
    } catch (err) {
      console.error("Payment Confirmation Error:", err);
    }
  };

  if (!isAuthenticated) {
    return (
      <Routes>
        <Route path="*" element={<LoginRegistration onLoginSuccess={handleLoginSuccess} />} />
      </Routes>
    );
  }

  return (
    <div className={`app-main-wrapper role-${currentRole}`}>
      {/* Top Header / User Context */}
      <header className="mobile-app-header">
        <div className="header-user-info">
          <p className="greeting">Welcome, {currentUser || 'User'}</p>
          <span className="role-badge">{currentRole}</span>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="header-action-btn theme-toggle" onClick={toggleTheme} aria-label="Toggle Theme">
             {isDark ? <Sun size={20} /> : <Moon size={20} />}
          </button>
          <button className="header-action-btn notif-btn" onClick={() => setShowNotifications(true)} aria-label="Notifications" style={{ position: 'relative' }}>
             <Bell size={20} />
             <span className="notif-badge"></span>
          </button>
          <button className="header-action-btn" onClick={handleSignOut} aria-label="Sign Out">
             <LogOut size={20} />
          </button>
        </div>
      </header>

      <main className="app-viewport">
        <Routes>
          <Route 
            path="/" 
            element={
              <Dashboard 
                currentRole={currentRole} 
                requests={globalRequests} 
                setShowReviewFor={setShowReviewFor} 
                setActiveChat={setActiveChat}
                setActiveCheckout={setActiveCheckout}
              />
            } 
          />
          <Route 
            path="/book" 
            element={
              <BookingWizard 
                currentRole={currentRole} 
                onClose={() => navigate('/')}
                onSuccess={handleBookingSuccess}
              />
            } 
          />
          <Route path="/tickets" element={<MemberTickets currentRole={currentRole} requests={globalRequests} />} />
          <Route path="/worker" element={<WorkerPortal requests={globalRequests} onUpdate={updateRequestStatus} currentUser={currentUser} />} />
          <Route path="/supervisor" element={<SupervisorConsole requests={globalRequests} onUpdate={updateRequestStatus} />} />
          <Route path="/director" element={<DirectorPortal />} />
          <Route path="/admin/verification" element={<WorkerVerification />} />
          <Route path="/admin/analytics" element={<AdminAnalytics />} />
          <Route path="/tracking" element={<TrackingMap />} />
        </Routes>
      </main>

      {/* Floating Bottom Nav Pill */}
      <nav className="floating-bottom-nav">
        <div className="nav-pill-container">
          
          {/* Specific Routing mapped by Role */}
          {(currentRole === 'member' || currentRole === 'chairman') && (
            <>
              <BottomNavLink to="/" icon={Home} />
              <BottomNavLink to="/book" icon={PlusCircle} />
              <BottomNavLink to="/tickets" icon={FileText} />
            </>
          )}

          {currentRole === 'worker' && (
            <BottomNavLink to="/worker" icon={Briefcase} />
          )}

          {currentRole === 'supervisor' && (
            <>
              <BottomNavLink to="/supervisor" icon={Home} />
              <BottomNavLink to="/admin/verification" icon={UserCircle} />
            </>
          )}

          {currentRole === 'director' && (
            <>
              <BottomNavLink to="/director" icon={Home} />
              <BottomNavLink to="/admin/analytics" icon={BarChart3} />
            </>
          )}
        </div>
      </nav>

      {/* Cross-Platform Review Trigger */}
      <AnimatePresence>
        {showReviewFor && (
          <ReviewModal 
            request={showReviewFor} 
            onClose={() => setShowReviewFor(null)} 
            onSubmit={handleReviewSubmit}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {activeChat && (
          <ChatWindow 
            request={activeChat}
            currentUser={currentUser}
            messages={activeChat.messages || []}
            onSendMessage={handleSendMessage}
            onClose={() => setActiveChat(null)}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {activeCheckout && (
          <PaymentCheckout 
            request={activeCheckout}
            onPaymentSuccess={handlePaymentSuccess}
            onClose={() => setActiveCheckout(null)}
          />
        )}
      </AnimatePresence>

      <NotificationCenter 
        isOpen={showNotifications} 
        onClose={() => setShowNotifications(false)} 
      />

      {/* Global Product Tour */}
      <ProductTour />

    </div>
  );
};

const App = () => {
  return (
    <ThemeProvider>
      <Router>
        <MainLayout />
      </Router>
    </ThemeProvider>
  );
};

export default App;
