import React from 'react';
import { motion } from 'framer-motion';
import { 
  FileText, Clock, CheckCircle2, AlertCircle, Zap, Shield
} from 'lucide-react';
import './MemberTickets.css';

const MemberTickets = ({ currentRole, requests = [] }) => {
  const tickets = requests.map(req => ({
    id: req.id,
    type: req.category === 'Security' || req.category === 'Housekeeping' ? 'Maintenance' : 'Amenity',
    title: req.issue || req.service,
    status: req.status,
    date: req.time,
    color: req.status === 'Resolved' ? '#94a3b8' : (req.status === 'Requested' ? '#3b82f6' : '#f59e0b')
  }));

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.1 } }
  };

  const ticketVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 300, damping: 24 } }
  };

  return (
    <div className="tickets-dashboard">
      <motion.div 
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="tickets-header"
      >
        <h2>My History & Tickets</h2>
        <p>Track all your service requests.</p>
      </motion.div>

      {tickets.length === 0 ? (
        <motion.div 
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="empty-tickets"
        >
          <div className="empty-icon-ring">
            <FileText size={32} />
          </div>
          <h3>No Active Tickets</h3>
          <p>You haven't requested any services yet.</p>
        </motion.div>
      ) : (
        <motion.div 
          className="digital-tickets-list"
          variants={containerVariants}
          initial="hidden"
          animate="visible"
        >
          {tickets.map((ticket) => (
             <motion.div 
               key={ticket.id}
               variants={ticketVariants}
               className={`digital-ticket ${ticket.status === 'Resolved' ? 'resolved' : 'active'}`}
               style={{ '--ticket-color': ticket.color }}
             >
               <div className="dt-left">
                 <div className="dt-type">
                   {ticket.type === 'Maintenance' ? <Zap size={12} /> : <Shield size={12} />}
                   {ticket.type}
                 </div>
                 <h3 className="dt-title">{ticket.title}</h3>
                 <div className="dt-date">
                   <Clock size={12} /> {ticket.date}
                 </div>
               </div>
               
               {/* Perforated Divider */}
               <div className="dt-divider">
                 <div className="notch top" />
                 <div className="dash-line" />
                 <div className="notch bottom" />
               </div>

               <div className="dt-right">
                 <div className="dt-status-icon" style={{ color: ticket.color }}>
                   {ticket.status === 'Resolved' || ticket.status === 'Confirmed' ? (
                     <CheckCircle2 size={28} />
                   ) : (
                     <Clock size={28} className="pulse-icon" />
                   )}
                 </div>
                 <span className="dt-status-text" style={{ color: ticket.color }}>
                   {ticket.status}
                 </span>
                 <span className="dt-id">{ticket.id}</span>
               </div>
             </motion.div>
          ))}
        </motion.div>
      )}
    </div>
  );
};

export default MemberTickets;
