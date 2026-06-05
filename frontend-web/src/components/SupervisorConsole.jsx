import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Building2, 
  AlertCircle, 
  CheckCircle2, 
  Clock, 
  Briefcase,
  TrendingUp,
  MessageSquare,
  Search,
  Filter
} from 'lucide-react';
import './SupervisorConsole.css';

const SupervisorConsole = ({ requests, onUpdate }) => {
  const [activeTab, setActiveTab] = useState('queries');
  const [searchQuery, setSearchQuery] = useState('');

  const kpis = [
    { label: 'Active Areas', value: '4', trend: 'Stable', icon: Building2, color: '#3b82f6' },
    { label: 'Open Issues', value: String(requests.filter(r => r.status !== 'Resolved').length), trend: 'Live', icon: AlertCircle, color: '#ef4444' },
    { label: 'SLA Compliance', value: '98.5%', trend: '+1.2%', icon: CheckCircle2, color: '#10b981' },
    { label: 'Active Staff', value: '315', trend: '+12', icon: Briefcase, color: '#8b5cf6' }
  ];

  const handleUpdate = (id, newStatus) => {
    onUpdate(id, newStatus);
    alert(`Successfully verified and updated status for ${id}.`);
  };

  return (
    <div className="supervisor-console-container">
      <header className="console-header">
        <div className="header-left">
          <h2>Operations Command Center</h2>
          <p>Centralized view of all society areas and ongoing issues.</p>
        </div>
        <div className="header-actions">
           <div className="search-bar">
             <Search size={18} className="search-icon" />
             <input 
               type="text" 
               placeholder="Search areas or queries..." 
               value={searchQuery}
               onChange={(e) => setSearchQuery(e.target.value)}
             />
           </div>
           <button className="btn-secondary"><Filter size={18} /> Filters</button>
        </div>
      </header>

      {/* KPI Analytics Bar */}
      <div className="kpi-banner">
        {kpis.map((kpi, idx) => (
          <motion.div 
            key={idx}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.1 }}
            className="kpi-box"
          >
            <div className="kpi-icon-box" style={{ backgroundColor: `${kpi.color}15`, color: kpi.color }}>
              {(() => {
                const Icon = kpi.icon;
                return <Icon size={24} />;
              })()}
            </div>
            <div className="kpi-content">
              <span className="kpi-label">{kpi.label}</span>
              <div className="kpi-value-row">
                <h3>{kpi.value}</h3>
                <span className={`trend-badge ${kpi.trend.startsWith('+') ? 'positive' : 'negative'}`}>
                  {kpi.trend}
                </span>
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      <div className="console-main">
        <div className="tabs-row">
          <button 
            className={`tab ${activeTab === 'queries' ? 'active' : ''}`}
            onClick={() => setActiveTab('queries')}
          >
            Issue Tracker
          </button>
          <button 
            className={`tab ${activeTab === 'facilities' ? 'active' : ''}`}
            onClick={() => setActiveTab('facilities')}
          >
            Area Management
          </button>
        </div>

        <div className="content-pane">
          {activeTab === 'queries' && (
            <div className="queries-list">
              {requests.map((query) => (
                <motion.div 
                  key={query.id} 
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="query-card"
                >
                  <div className="query-meta">
                    <span className="q-id">{query.id}</span>
                    <span className={`priority-tag ${query.priority.toLowerCase()}`}>{query.priority}</span>
                    <span className="q-time"><Clock size={14}/> {query.time}</span>
                  </div>
                  <h3 className="q-title">{query.issue}</h3>
                  <div className="q-footer">
                    <div className="q-facility"><Building2 size={16}/> {query.location}</div>
                    <div className="q-reporter"><MessageSquare size={16}/> Reported by: {query.reporter}</div>
                    <div className="q-actions">
                      <select 
                        className={`status-dropdown ${(query.status).toLowerCase().replace(/\s+/g, '-')}`} 
                        value={query.status}
                        onChange={(e) => handleUpdate(query.id, e.target.value)}
                      >
                        <option value="Requested">Requested</option>
                        <option value="Investigating">Investigating</option>
                        <option value="In Progress">In Progress</option>
                        <option value="Resolved">Resolved</option>
                      </select>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          )}

          {activeTab === 'facilities' && (
             <div className="empty-state">
               <Building2 size={48} className="empty-icon" />
               <h3>Area Overview</h3>
               <p>Select a society block from the sidebar to view detailed operations metrics.</p>
             </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SupervisorConsole;
