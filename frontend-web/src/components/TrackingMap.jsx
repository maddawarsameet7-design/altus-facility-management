import React, { useState, useEffect } from 'react';
import './TrackingMap.css';

const TrackingMap = () => {
  const [progress, setProgress] = useState(0);

  // Simulating real-time movement for the demo
  useEffect(() => {
    const interval = setInterval(() => {
      setProgress(prev => (prev >= 100 ? 0 : prev + 0.5));
    }, 100);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="tracking-map-container">
      <div className="map-header">
        <div className="status-dot-pulsing"></div>
        <h3>Live Service Partner Tracking</h3>
      </div>
      
      <div className="map-canvas">
        {/* Mock Map Background Grid */}
        <div className="map-grid"></div>
        
        {/* Destination Marker */}
        <div className="marker destination">
          <div className="marker-pin">🏥</div>
          <span className="marker-label">City Care Hospital</span>
        </div>

        {/* Moving Worker Marker */}
        <div 
          className="marker worker" 
          style={{ 
            left: `${15 + (progress * 0.65)}%`, 
            top: `${70 - (progress * 0.4)}%` 
          }}
        >
          <div className="marker-icon">🚶‍♂️</div>
          <div className="worker-tooltip">
            <strong>Rajesh K.</strong>
            <span>3 mins away</span>
          </div>
        </div>

        {/* Path Line */}
        <svg className="path-svg">
          <line x1="15%" y1="70%" x2="80%" y2="30%" className="path-line-background" />
          <line 
            x1="15%" y1="70%" 
            x2={`${15 + (progress * 0.65)}%`} 
            y2={`${70 - (progress * 0.4)}%`} 
            className="path-line-progress" 
          />
        </svg>
      </div>

      <div className="map-footer">
        <div className="info-pill">
          <span className="label">Estimated Arrival</span>
          <span className="value">08:42 AM</span>
        </div>
        <div className="info-pill">
          <span className="label">Distance</span>
          <span className="value">1.2 km</span>
        </div>
      </div>
    </div>
  );
};

export default TrackingMap;
