import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Building2, User, Navigation2, Clock, Map as MapIcon } from 'lucide-react';
import './TrackingMap.css';

const TrackingMap = () => {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setProgress(prev => (prev >= 100 ? 0 : prev + 0.3));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="tracking-map-container">
      <div className="map-view">
        <div className="map-grid-overlay"></div>
        
        {/* Connection Path */}
        <svg className="map-path-layer">
          <line x1="20%" y1="80%" x2="80%" y2="20%" className="path-bg" />
          <motion.line 
            x1="20%" y1="80%" 
            x2={`${20 + (progress * 0.6)}%`} 
            y2={`${80 - (progress * 0.6)}%`} 
            className="path-fill" 
          />
        </svg>

        {/* Destination: Hospital */}
        <div className="map-marker location-hospital" style={{ top: '20%', right: '20%' }}>
          <div className="marker-core">
            <Building2 size={20} />
          </div>
          <div className="marker-label">City Care</div>
        </div>

        {/* Moving Asset: Staff */}
        <motion.div 
          className="map-marker location-staff" 
          style={{ 
            left: `${20 + (progress * 0.6)}%`, 
            top: `${80 - (progress * 0.6)}%` 
          }}
        >
          <div className="marker-core">
            <User size={20} strokeWidth={2.5} />
          </div>
          <div className="marker-callout">
            <span className="staff-name">Rajesh K.</span>
            <span className="eta-tag">3 min away</span>
          </div>
        </motion.div>
      </div>

      <div className="map-details-footer">
        <div className="map-stat">
          <Clock size={14} className="stat-icon" />
          <div className="stat-text">
            <span className="label">Exp. Arrival</span>
            <span className="value">08:42 AM</span>
          </div>
        </div>
        <div className="map-stat">
          <Navigation2 size={14} className="stat-icon" />
          <div className="stat-text">
            <span className="label">Distance</span>
            <span className="value">1.2 km</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TrackingMap;
