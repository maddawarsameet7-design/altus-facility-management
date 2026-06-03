import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Plus, 
  Settings, 
  MapPin, 
  ChevronRight,
  Zap,
  Droplets,
  Trash2,
  AlertCircle,
  TrendingUp,
  FileText,
  Phone,
  Star as StarIcon,
  MessageCircle,
  CreditCard
} from 'lucide-react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import { useNavigate } from 'react-router-dom';
import ReportIssueModal from './ReportIssueModal';
import BookingWizard from './BookingWizard';
import './Dashboard.css';

const Dashboard = ({ currentRole, requests, onBookingSuccess, setShowReviewFor, setActiveChat, setActiveCheckout }) => {
  const [showWizard, setShowWizard] = useState(false);
  const [showReportModal, setShowReportModal] = useState(false);
  const navigate = useNavigate();

  // Fix for Leaflet marker icon in React
  const customIcon = new L.Icon({
    iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
    iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
    shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
  });

  return (
    <div className="mobile-dashboard">
      
      {/* Dark Hero Card matching Reference Image */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="hero-card shadow-glass"
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <div style={{ background: 'rgba(255,255,255,0.1)', padding: '6px 12px', borderRadius: '100px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: 12, height: 6, background: 'var(--accent-green)', borderRadius: '10px' }} />
            <span>Facility Status: Optimal</span>
          </div>
          <button 
            style={{ background: 'transparent', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', padding: '4px' }} 
            onClick={() => alert('Settings configuration panel is currently under construction.')}
            aria-label="Settings"
          >
            <Settings size={20} style={{ color: 'rgba(255,255,255,0.6)', transition: 'color 0.2s' }} onMouseOver={(e) => e.target.style.color = '#fff'} onMouseOut={(e) => e.target.style.color = 'rgba(255,255,255,0.6)'} />
          </button>
        </div>

        {currentRole === 'chairman' && (
          <div style={{ textAlign: 'center', marginBottom: '32px' }}>
            <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: '14px', marginBottom: '8px' }}>
              Monthly Operational Cost
            </p>
            <h2 style={{ fontSize: '42px', fontWeight: '800', letterSpacing: '-1px' }}>
              ₹23,400.00
            </h2>
          </div>
        )}

        {/* Circular Action Buttons */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: '24px' }}>
          <button className="hero-action-btn" onClick={() => setShowWizard(true)}>
            <div className="hero-btn-icon"><Plus size={20} /></div>
            <span>Request</span>
          </button>
          
          {currentRole === 'member' && (
            <button className="hero-action-btn" onClick={() => setShowReportModal(true)}>
              <div className="hero-btn-icon"><AlertCircle size={20} /></div>
              <span>Complain</span>
            </button>
          )}

          <button className="hero-action-btn" onClick={() => navigate('/tickets')}>
            <div className="hero-btn-icon"><FileText size={20} /></div>
            <span>History</span>
          </button>
        </div>
      </motion.div>

      {/* Amenities & Tracking Section (The "Goals" section from reference) */}
      <div className="section-title">
        <span>Active Amenities</span>
        <a href="#" className="section-link">View all <ChevronRight size={14}/></a>
      </div>

      <div className="amenities-list">
        {requests.map((item, idx) => {
          const Icon = item.icon;
          return (
            <motion.div 
              key={item.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1 }}
              className="white-card amenity-card"
            >
              <div className="amenity-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                   <div style={{ padding: '10px', background: 'rgba(0,0,0,0.03)', borderRadius: '12px', color: item.color }}>
                     <Icon size={20} />
                   </div>
                   <div>
                     <h3 style={{ fontSize: '15px', fontWeight: '700' }}>{item.service}</h3>
                     <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{item.location}</p>
                   </div>
                </div>
                <ChevronRight size={18} style={{ color: 'var(--text-muted)' }} />
              </div>

              <div className="amenity-progress-area">
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '13px', fontWeight: '600' }}>
                  <span>{item.cost}</span>
                  <span style={{ color: item.status === 'Resolved' ? 'var(--accent-green)' : 'var(--accent-blue)' }}>
                    {item.status}
                  </span>
                </div>
                {/* Thick Progress Bar */}
                <div className="progress-track">
                  <div 
                    className="progress-fill" 
                    style={{ 
                      width: `${item.progress}%`, 
                      background: item.status === 'Resolved' ? 'var(--accent-green)' : (item.status === 'Investigating' ? 'var(--accent-orange)' : 'var(--accent-blue)')
                    }} 
                  />
                </div>
              </div>

              {/* LIVE TRACKING & WORKER INFO */}
              {item.worker && (
                <div className="worker-assignment-pane animate-slide-up">
                  <div className="worker-info-row">
                    <div className="worker-avatar">
                      {item.worker.name.charAt(0).toUpperCase()}
                    </div>
                    <div className="worker-meta">
                      <span className="worker-name">{item.worker.name}</span>
                      <div className="worker-stats">
                        <StarIcon size={12} fill="var(--accent-orange)" color="transparent" />
                        <span>{item.worker.rating}</span>
                        <span className="dot">•</span>
                        <span>Verified Professional</span>
                      </div>
                    </div>
                    <a href={`tel:${item.worker.phone}`} className="worker-call-btn" title="Call Worker">
                      <Phone size={16} />
                    </a>
                    <button 
                      className="worker-chat-btn" 
                      onClick={(e) => { e.stopPropagation(); setActiveChat(item); }}
                      title="Chat with Worker"
                    >
                      <MessageCircle size={16} />
                    </button>
                  </div>

                  {/* MINI MAP VIEW */}
                  {item.status === 'In Progress' && item.worker.location && (
                    <div className="mini-map-container">
                      <MapContainer 
                        center={[item.worker.location.lat || 19.076, item.worker.location.lng || 72.877]} 
                        zoom={15} 
                        scrollWheelZoom={false}
                        style={{ height: '120px', width: '100%', borderRadius: '12px' }}
                        zoomControl={false}
                        attributionControl={false}
                      >
                        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                        <Marker position={[item.worker.location.lat || 19.076, item.worker.location.lng || 72.877]} icon={customIcon}>
                          <Popup>Worker is here</Popup>
                        </Marker>
                      </MapContainer>
                      <div className="map-overlay-badge">Live Tracking</div>
                    </div>
                  )}

                  {/* ACTIONS FOR RESOLVED JOBS */}
                  {item.status === 'Resolved' && (
                    <div style={{ display: 'flex', gap: '8px', width: '100%' }}>
                      {!item.is_paid ? (
                        <button 
                          className="btn-pay-now"
                          onClick={(e) => { e.stopPropagation(); setActiveCheckout(item); }}
                        >
                          Pay {item.cost} <CreditCard size={16} style={{ marginLeft: '8px' }} />
                        </button>
                      ) : (
                        <button 
                          className="btn-rate-now"
                          onClick={(e) => { e.stopPropagation(); setShowReviewFor(item); }}
                        >
                          Rate Service <StarIcon size={16} style={{ marginLeft: '8px' }} />
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}
            </motion.div>
          )
        })}
      </div>

      {/* Modals */}
      <AnimatePresence>
        {showWizard && (
          <BookingWizard 
            currentRole={currentRole}
            onClose={() => setShowWizard(false)} 
            onSuccess={onBookingSuccess}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showReportModal && (
           <ReportIssueModal 
             onClose={() => setShowReportModal(false)}
             onSubmit={() => setShowReportModal(false)}
           />
        )}
      </AnimatePresence>

    </div>
  );
};

export default Dashboard;
