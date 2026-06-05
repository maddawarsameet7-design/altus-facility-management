import React from 'react';
import { motion } from 'framer-motion';
import { 
  TrendingUp, Building2, Shield, Users, Activity,
  Briefcase, ArrowUpRight, DollarSign
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
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0 }
  };

  return (
    <div className="executive-dashboard-light">
      <header className="ed-header">
        <div className="ed-header-left">
          <Activity size={28} className="text-blue" />
          <div>
            <h1>Executive Dashboard</h1>
            <p>Altsan Platform Overview</p>
          </div>
        </div>
        <div className="ed-date-pill">
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
        <motion.div variants={itemVariants} className="ed-card ed-hero">
          <div className="ed-hero-bg"></div>
          <div className="ed-hero-content">
            <div className="hero-top">
              <span className="hero-badge"><Building2 size={14}/> Society Budget (YTD)</span>
            </div>
            <div className="hero-main">
              <h2>₹1,240,500</h2>
              <div className="hero-trend">
                <ArrowUpRight size={16} />
                <span>+12.4% vs last quarter</span>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Quick Stats Grid */}
        <motion.div variants={itemVariants} className="ed-card stat-card">
          <div className="stat-icon-wrap text-blue"><Users size={20} /></div>
          <div className="stat-details">
            <span className="stat-label">Active Members</span>
            <span className="stat-value">2,845</span>
          </div>
        </motion.div>

        <motion.div variants={itemVariants} className="ed-card stat-card">
          <div className="stat-icon-wrap text-green"><DollarSign size={20} /></div>
          <div className="stat-details">
            <span className="stat-label">Net Profit / Mo</span>
            <span className="stat-value">₹42k</span>
          </div>
        </motion.div>

        {/* Financial Analytics Chart */}
        <motion.div variants={itemVariants} className="ed-card chart-card">
          <div className="card-header">
            <h3>Revenue Analytics</h3>
            <button className="btn-filter">Last 6 Months</button>
          </div>
          <div className="chart-container">
            {analyticsData.map((data, i) => (
              <div key={i} className="chart-bar-wrap">
                <motion.div 
                  className="chart-bar"
                  initial={{ height: 0 }}
                  animate={{ height: `${data.val}%` }}
                  transition={{ duration: 1, delay: 0.2 + (i * 0.1), type: 'spring' }}
                />
                <span className="chart-label">{data.month}</span>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Top Agencies */}
        <motion.div variants={itemVariants} className="ed-card agencies-card">
          <div className="card-header">
            <h3>Top Performing Agencies</h3>
            <span className="view-all">View All</span>
          </div>
          <div className="agencies-list">
            {topAgencies.map((agency, idx) => (
              <div key={idx} className="agency-row">
                <div className="agency-left">
                  <div className="agency-icon" style={{ color: agency.color, background: `${agency.color}15` }}>
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
    </div>
  );
};

export default DirectorPortal;
