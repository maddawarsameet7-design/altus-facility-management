import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertCircle, X, MapPin } from 'lucide-react';
import './IsometricMap.css';

const IsometricMap = ({ requests = [] }) => {
  const [selectedBuilding, setSelectedBuilding] = useState(null);

  const buildings = [
    { id: 'tower_a', name: 'Tower A', x: 20, y: 30, h: 120 },
    { id: 'tower_b', name: 'Tower B', x: 60, y: 20, h: 140 },
    { id: 'clubhouse', name: 'Clubhouse', x: 40, y: 60, h: 60 }
  ];

  // Logic to determine if a building has an active alert
  // For demo purposes, we will hardcode Tower A to have an alert if ANY request exists, 
  // or parse the location string.
  const getAlertForBuilding = (bId) => {
    if (requests.length === 0) return null;
    if (bId === 'tower_a') return requests[0]; // mock top alert for Tower A
    if (bId === 'clubhouse' && requests.length > 1) return requests[1];
    return null;
  };

  return (
    <div className="iso-map-container">
      <div className="iso-grid-wrapper">
        <div className="iso-grid">
          {buildings.map((b) => {
            const activeAlert = getAlertForBuilding(b.id);
            const isPulsing = !!activeAlert;
            
            return (
              <div 
                key={b.id} 
                className={`iso-building ${isPulsing ? 'alerting' : ''} ${selectedBuilding?.id === b.id ? 'selected' : ''}`}
                style={{ 
                  left: `${b.x}%`, 
                  top: `${b.y}%`,
                  '--b-height': `${b.h}px`
                }}
                onClick={() => setSelectedBuilding(b)}
              >
                {/* 3D Faces */}
                <div className="face top"></div>
                <div className="face left" style={{ height: `${b.h}px` }}></div>
                <div className="face right" style={{ height: `${b.h}px` }}></div>
                
                {/* Alert Beacon */}
                {isPulsing && (
                  <div className="iso-beacon">
                    <div className="beacon-pulse"></div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <AnimatePresence>
        {selectedBuilding && (
          <motion.div 
            className="building-popup"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
          >
            <div className="bp-header">
              <h3>{selectedBuilding.name}</h3>
              <button onClick={() => setSelectedBuilding(null)}><X size={16}/></button>
            </div>
            <div className="bp-content">
              {getAlertForBuilding(selectedBuilding.id) ? (
                <div className="bp-alert">
                  <AlertCircle size={20} className="text-red" />
                  <div>
                    <strong>Active Incident</strong>
                    <p>{getAlertForBuilding(selectedBuilding.id).service} Issue</p>
                  </div>
                </div>
              ) : (
                <div className="bp-status-ok">
                  <MapPin size={16} />
                  <span>All Systems Nominal</span>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default IsometricMap;
