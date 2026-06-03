import React from 'react';
import { motion } from 'framer-motion';
import { 
  FileText, 
  Clock, 
  CheckCircle2, 
  AlertCircle 
} from 'lucide-react';
import './Dashboard.css'; // Inheriting the mobile UI layouts

const MemberTickets = ({ currentRole, requests = [] }) => {
  // Mapping global requests to the history list format
  const tickets = requests.map(req => ({
    id: req.id,
    type: req.category === 'Security' || req.category === 'Housekeeping' ? 'Maintenance' : 'Amenity',
    title: req.issue || req.service,
    status: req.status,
    date: req.time,
    color: req.status === 'Resolved' ? 'var(--text-soft)' : (req.status === 'Requested' ? 'var(--accent-blue)' : 'var(--accent-orange)')
  }));

  return (
    <div className="mobile-dashboard">
      <motion.div 
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="section-title"
        style={{ marginTop: '12px' }}
      >
        <span>My History & Tickets</span>
        <FileText size={18} style={{ color: 'var(--text-muted)' }} />
      </motion.div>

      <div className="amenities-list">
        {tickets.map((ticket, idx) => (
           <motion.div 
             key={ticket.id}
             initial={{ opacity: 0, x: -20 }}
             animate={{ opacity: 1, x: 0 }}
             transition={{ delay: idx * 0.1 }}
             className="white-card amenity-card"
             style={{ padding: '20px' }}
           >
             <div className="amenity-header" style={{ marginBottom: '12px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                   <span style={{ fontSize: '11px', fontWeight: '700', color: ticket.color, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                     {ticket.type} • {ticket.id}
                   </span>
                   <h3 style={{ fontSize: '15px', fontWeight: '700' }}>{ticket.title}</h3>
                </div>
                {ticket.status === 'Resolved' || ticket.status === 'Confirmed' ? (
                  <CheckCircle2 size={24} style={{ color: ticket.color }} />
                ) : (
                  <Clock size={24} style={{ color: ticket.color }} />
                )}
             </div>
             
             <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid rgba(0,0,0,0.04)', paddingTop: '12px' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Clock size={12}/> {ticket.date}
                </span>
                <span style={{ fontSize: '12px', fontWeight: '600', color: ticket.status === 'Resolved' ? 'var(--text-soft)' : 'var(--text-main)' }}>
                  {ticket.status}
                </span>
             </div>
           </motion.div>
        ))}
      </div>

      {tickets.length === 0 && (
        <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
          <AlertCircle size={32} style={{ margin: '0 auto 12px auto', opacity: 0.5 }} />
          <p>No tickets or requests found.</p>
        </div>
      )}
    </div>
  );
};

export default MemberTickets;
