import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Building2, AlertCircle, CheckCircle2, Clock, Briefcase, TrendingUp,
  MessageSquare, Search, Filter, ShieldCheck, Activity, MapPin, Zap
} from 'lucide-react';
import './SupervisorConsole.css';

const SupervisorConsole = ({ requests, onUpdate }) => {
  const [activeTab, setActiveTab] = useState('queries');
  const [searchQuery, setSearchQuery] = useState('');

  const kpis = [
    { label: 'Active Zones', value: '4', trend: 'Stable', icon: Building2, color: '#3b82f6' },
    { label: 'Live Issues', value: String(requests.filter(r => r.status !== 'Resolved').length), trend: 'Critical', icon: AlertCircle, color: '#ef4444' },
    { label: 'SLA Met', value: '98.5%', trend: '+1.2%', icon: ShieldCheck, color: '#10b981' },
    { label: 'Staff Online', value: '315', trend: '+12', icon: Briefcase, color: '#8b5cf6' }
  ];

  const handleStatusChange = (id, newStatus) => {
    onUpdate(id, newStatus);
  };

  const statuses = ['Requested', 'Investigating', 'In Progress', 'Resolved'];

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.1 } }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0 }
  };

  return (
    <div className="command-center-container">
      <header className="cc-header">
        <div className="cc-header-top">
          <div className="cc-brand">
            <Activity size={28} color="#3b82f6" />
            <div>
              <h2>Command Center</h2>
              <p>Altsan Global Operations</p>
            </div>
          </div>
          <div className="cc-search">
            <Search size={18} className="search-icon" />
            <input 
              type="text" 
              placeholder="Track issues, areas, or staff..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>
      </header>

      {/* KPI HUD */}
      <motion.div 
        className="kpi-hud"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        {kpis.map((kpi, idx) => {
          const Icon = kpi.icon;
          return (
            <motion.div key={idx} variants={itemVariants} className="kpi-glass-widget">
              <div className="kpi-bg-glow" style={{ background: kpi.color }} />
              <div className="kpi-top">
                <div className="kpi-icon" style={{ color: kpi.color, background: `${kpi.color}20` }}>
                  <Icon size={20} />
                </div>
                <span className={`kpi-trend ${kpi.trend === 'Critical' ? 'danger' : 'success'}`}>
                  {kpi.trend}
                </span>
              </div>
              <div className="kpi-bottom">
                <h3>{kpi.value}</h3>
                <p>{kpi.label}</p>
              </div>
            </motion.div>
          );
        })}
      </motion.div>

      <div className="cc-main">
        <div className="cc-tabs">
          <button className={`cc-tab ${activeTab === 'queries' ? 'active' : ''}`} onClick={() => setActiveTab('queries')}>
            Live Dispatch
          </button>
          <button className={`cc-tab ${activeTab === 'facilities' ? 'active' : ''}`} onClick={() => setActiveTab('facilities')}>
            Facility Map
          </button>
        </div>

        <div className="cc-content">
          {activeTab === 'queries' && (
            <motion.div className="dispatch-list" variants={containerVariants} initial="hidden" animate="visible">
              {requests.map(req => (
                <motion.div key={req.id} variants={itemVariants} className="dispatch-row">
                  <div className="d-left">
                    <div className="d-meta">
                      <span className="d-id">{req.id}</span>
                      <span className={`d-priority ${req.priority.toLowerCase()}`}>
                        <Zap size={12} /> {req.priority}
                      </span>
                    </div>
                    <h4 className="d-title">{req.issue}</h4>
                    <div className="d-details">
                      <span><MapPin size={14} /> {req.location}</span>
                      <span><MessageSquare size={14} /> {req.reporter}</span>
                    </div>
                  </div>
                  
                  <div className="d-right">
                    <div className="status-stepper">
                      {statuses.map(status => {
                        const currentIndex = statuses.indexOf(req.status);
                        const statusIndex = statuses.indexOf(status);
                        const isActive = req.status === status;
                        const isPast = statusIndex < currentIndex;
                        
                        let stateClass = '';
                        if (isActive) stateClass = 'active pulse';
                        else if (isPast) stateClass = 'completed';
                        
                        return (
                          <button 
                            key={status}
                            className={`stepper-btn ${stateClass}`}
                            onClick={() => handleStatusChange(req.id, status)}
                            title={`Mark as ${status}`}
                          >
                            {status === 'Resolved' && isActive ? <CheckCircle2 size={16} /> : <div className="step-dot" />}
                            <span className="step-label">{status}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </motion.div>
              ))}
            </motion.div>
          )}

          {activeTab === 'facilities' && (
             <div className="cc-empty-state">
               <Building2 size={64} style={{ opacity: 0.2, marginBottom: '16px' }} />
               <h3>Area Operations Radar</h3>
               <p>Select a zone from the sidebar to view live sensor data.</p>
             </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SupervisorConsole;
