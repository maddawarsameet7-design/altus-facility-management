import React from 'react';
import { motion } from 'framer-motion';
import { 
  TrendingUp, Building2, Shield, Users, Activity,
  Briefcase, ArrowUpRight, DollarSign, BellRing, ChevronRight,
  Filter, Download, Share2
} from 'lucide-react';
import './DirectorPortal.css';

const DirectorPortal = () => {
  const analyticsData = [
    { month: 'Jan', val: 40 },
    { month: 'Feb', val: 70 },
    { month: 'Mar', val: 45 },
    { month: 'Apr', val: 90 },
    { month: 'May', val: 65 },
    { month: 'Jun', val: 85 }
  ];

  const topAgencies = [
    { name: 'Elite Cleaners Corp', rating: 4.9, cost: '₹2,400', color: '#10b981', category: 'Cleaning' },
    { name: 'Society Shine Plumbers', rating: 4.7, cost: '₹1,850', color: '#f59e0b', category: 'Maintenance' },
    { name: 'City Secure Guards', rating: 4.8, cost: '₹3,200', color: '#3b82f6', category: 'Security' }
  ];

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.1 } }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 30 },
    visible: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } }
  };

  return (
    <div className="executive-dashboard-light">
      <div className="ed-bg-mesh"></div>
      
      <header className="ed-header">
        <div className="ed-header-left">
          <div className="ed-icon-glass">
            <Activity size={28} className="text-blue" />
          </div>
          <div>
            <h1>Executive Command Center</h1>
            <p>Altsan Platform Overview</p>
          </div>
        </div>
        <div className="ed-date-pill glass-pill">
          As of June 2026
        </div>
      </header>

      <motion.div 
        className="ed-grid"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        {/* Main Financial Hero */}
        <motion.div variants={itemVariants} className="ed-card ed-hero glass-card">
          <div className="ed-hero-bg"></div>
          <div className="ed-hero-content">
            <div className="hero-top">
              <span className="hero-badge"><Building2 size={14}/> Society Budget (YTD)</span>
            </div>
            <div className="hero-main">
              <h2>₹12,40,500</h2>
              <div className="hero-trend">
                <ArrowUpRight size={18} />
                <span>+12.4% vs last quarter</span>
              </div>
            </div>
            <div className="hero-glow"></div>
          </div>
        </motion.div>

        {/* Quick Stats Grid */}
        <motion.div variants={itemVariants} className="ed-card stat-card glass-card">
          <div className="stat-icon-wrap text-blue glow-blue"><Users size={24} /></div>
          <div className="stat-details">
            <span className="stat-label">Active Members</span>
            <span className="stat-value">2,845</span>
          </div>
        </motion.div>

        <motion.div variants={itemVariants} className="ed-card stat-card glass-card">
          <div className="stat-icon-wrap text-green glow-green"><DollarSign size={24} /></div>
          <div className="stat-details">
            <span className="stat-label">Net Profit / Mo</span>
            <span className="stat-value">₹42k</span>
          </div>
        </motion.div>

        {/* Active Alerts - NEW SECTION */}
        <motion.div variants={itemVariants} className="ed-card alerts-card glass-card">
          <div className="card-header">
            <h3><BellRing size={18} className="text-orange" style={{marginRight: '8px', display: 'inline'}} /> Priority Alerts</h3>
            <span className="view-all">Manage</span>
          </div>
          <div className="alerts-list">
            <div className="alert-item critical">
              <div className="alert-dot"></div>
              <div className="alert-text">
                <strong>Generator Failure</strong>
                <span>Tower B Backup System</span>
              </div>
              <ChevronRight size={16} className="text-muted" />
            </div>
            <div className="alert-item warning">
              <div className="alert-dot"></div>
              <div className="alert-text">
                <strong>Vendor Contract Expiring</strong>
                <span>City Secure Guards (3 days left)</span>
              </div>
              <ChevronRight size={16} className="text-muted" />
            </div>
          </div>
        </motion.div>

        {/* Financial Analytics Chart */}
        <motion.div variants={itemVariants} className="ed-card chart-card glass-card">
          <div className="card-header">
            <h3>Revenue Analytics</h3>
            <button className="btn-filter glass-btn">Last 6 Months</button>
          </div>
          <div className="chart-container">
            {analyticsData.map((data, i) => (
              <div key={i} className="chart-bar-wrap">
                <div className="chart-bar-track">
                  <motion.div 
                    className="chart-bar-fill"
                    initial={{ height: 0 }}
                    animate={{ height: `${data.val}%` }}
                    transition={{ duration: 1.5, delay: 0.2 + (i * 0.1), type: 'spring', bounce: 0.4 }}
                  />
                </div>
                <span className="chart-label">{data.month}</span>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Top Agencies */}
        <motion.div variants={itemVariants} className="ed-card agencies-card glass-card">
          <div className="card-header">
            <h3>Top Performing Agencies</h3>
            <span className="view-all">View All</span>
          </div>
          <div className="agencies-list">
            {topAgencies.map((agency, idx) => (
              <div key={idx} className="agency-row premium-row">
                <div className="agency-left">
                  <div className="agency-icon" style={{ color: agency.color, background: `${agency.color}15`, boxShadow: `0 0 15px ${agency.color}20` }}>
                    {agency.category === 'Security' ? <Shield size={20} /> : <Briefcase size={20} />}
                  </div>
                  <div className="agency-info">
                    <h4>{agency.name}</h4>
                    <span>{agency.category} • ⭐ {agency.rating}</span>
                  </div>
                </div>
                <div className="agency-right">
                  <strong>{agency.cost}</strong>
                  <span>Paid / Month</span>
                </div>
              </div>
            ))}
          </div>
        </motion.div>

      </motion.div>

      {/* 1-Handed Bottom Command Bar */}
      <motion.div 
        className="ed-bottom-command-bar"
        initial={{ y: "100%" }}
        animate={{ y: 0 }}
        transition={{ type: "spring", damping: 25, stiffness: 200, delay: 0.5 }}
      >
        <button className="command-btn primary-action">
          <Filter size={20} />
          <span>Filters</span>
        </button>
        
        <div className="command-secondary-actions">
          <button className="command-icon-btn">
            <Download size={18} />
          </button>
          <button className="command-icon-btn">
            <Share2 size={18} />
          </button>
        </div>
      </motion.div>

    </div>
  );
};

export default DirectorPortal;
