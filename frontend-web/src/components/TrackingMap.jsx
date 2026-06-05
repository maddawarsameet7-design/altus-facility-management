import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Building2, Navigation2, Clock, Phone, MessageSquare, ShieldCheck, MapPin } from 'lucide-react';
import './TrackingMap.css';

const TrackingMap = () => {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setProgress(prev => (prev >= 100 ? 0 : prev + 0.5));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="uber-tracking-container">
      {/* Map Background layer */}
      <div className="uber-map-view">
        <div className="uber-map-grid"></div>
        
        {/* Route Path */}
        <svg className="uber-map-path">
          <line x1="20%" y1="70%" x2="70%" y2="30%" className="path-trace" />
          <motion.line 
            x1="20%" y1="70%" 
            x2={`${20 + (progress * 0.5)}%`} 
            y2={`${70 - (progress * 0.4)}%`} 
            className="path-active" 
          />
        </svg>

        {/* Destination Pin */}
        <div className="uber-pin destination-pin" style={{ top: '30%', left: '70%' }}>
          <div className="pin-circle">
            <Building2 size={18} />
          </div>
          <div className="pin-pulse"></div>
          <div className="pin-label">Lobby B</div>
        </div>

        {/* Moving Worker Car/Pin */}
        <motion.div 
          className="uber-pin worker-pin" 
          style={{ 
            left: `${20 + (progress * 0.5)}%`, 
            top: `${70 - (progress * 0.4)}%` 
          }}
        >
          <div className="worker-avatar-small">
            <img src="https://i.pravatar.cc/100?img=11" alt="Worker" />
          </div>
          <div className="eta-badge">
            3 min
          </div>
        </motion.div>
      </div>

      {/* Bottom Floating UI (Uber Style) */}
      <motion.div 
        className="uber-bottom-sheet"
        initial={{ y: "100%" }}
        animate={{ y: 0 }}
        transition={{ type: "spring", damping: 25, stiffness: 200 }}
      >
        <div className="sheet-handle"></div>
        
        <div className="eta-header">
          <div className="eta-left">
            <h2>Arriving in 3 mins</h2>
            <p>Your maintenance unit is on the way</p>
          </div>
          <div className="eta-right">
            <div className="eta-time-block">
               <strong>08:42</strong>
               <span>AM</span>
            </div>
          </div>
        </div>

        <div className="worker-profile-card">
          <div className="wp-left">
            <div className="wp-avatar">
              <img src="https://i.pravatar.cc/150?img=11" alt="Rajesh K." />
              <div className="wp-badge"><ShieldCheck size={12}/></div>
            </div>
            <div className="wp-info">
              <h3>Rajesh K.</h3>
              <div className="wp-rating">
                 ⭐ 4.9 <span>(124 jobs)</span>
              </div>
            </div>
          </div>
          <div className="wp-right">
            <div className="vehicle-badge">
              Unit 42
            </div>
          </div>
        </div>

        <div className="job-summary">
          <div className="js-row">
            <MapPin size={16} className="js-icon text-blue" />
            <div className="js-text">
               <strong>Lobby B, Floor 3</strong>
               <span>Plumbing Leak</span>
            </div>
          </div>
        </div>

        <div className="action-footer">
          <button className="btn-action secondary">
            <MessageSquare size={20} />
            Message
          </button>
          <button className="btn-action primary">
            <Phone size={20} />
            Contact Unit
          </button>
        </div>
      </motion.div>
    </div>
  );
};

export default TrackingMap;
