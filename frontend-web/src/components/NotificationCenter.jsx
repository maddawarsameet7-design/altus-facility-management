import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Bell, Info, AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import './NotificationCenter.css';

const NotificationCenter = ({ isOpen, onClose }) => {
  // Mock notifications array
  const notifications = [
    {
      id: 1,
      type: 'alert',
      title: 'Urgent HVAC Maintenance',
      message: 'Ticket #4920 in Tower A needs immediate attention.',
      time: 'Just now',
      read: false
    },
    {
      id: 2,
      type: 'success',
      title: 'Payment Processed',
      message: '₹12,500 has been credited to your account.',
      time: '2 hours ago',
      read: false
    },
    {
      id: 3,
      type: 'info',
      title: 'New Policy Update',
      message: 'Please review the updated safety guidelines for Q3.',
      time: '1 day ago',
      read: true
    },
    {
      id: 4,
      type: 'info',
      title: 'System Maintenance',
      message: 'Altsan Core will be offline from 2AM-4AM on Sunday.',
      time: '2 days ago',
      read: true
    }
  ];

  const getIcon = (type) => {
    switch(type) {
      case 'alert': return <AlertTriangle size={20} className="text-orange" />;
      case 'success': return <CheckCircle size={20} className="text-green" />;
      default: return <Info size={20} className="text-blue" />;
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div 
            className="nc-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div 
            className="nc-panel"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
          >
            <div className="nc-header">
              <div className="nc-header-left">
                <Bell size={24} className="text-blue" />
                <h2>Notifications</h2>
              </div>
              <button className="nc-close-btn" onClick={onClose}>
                <X size={20} />
              </button>
            </div>

            <div className="nc-actions">
              <span className="unread-count">2 Unread</span>
              <button className="mark-read-btn">Mark all as read</button>
            </div>

            <div className="nc-list">
              {notifications.map((notif) => (
                <div key={notif.id} className={`nc-item ${notif.read ? 'read' : 'unread'}`}>
                  {!notif.read && <div className="unread-dot"></div>}
                  <div className="nc-item-icon">
                    {getIcon(notif.type)}
                  </div>
                  <div className="nc-item-content">
                    <h4>{notif.title}</h4>
                    <p>{notif.message}</p>
                    <div className="nc-item-time">
                      <Clock size={12} />
                      <span>{notif.time}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            
            <div className="nc-footer">
              <button className="view-all-btn">View All History</button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export default NotificationCenter;
