import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { dashboardApi, societyApi } from '../utils/api';
import { 
  TrendingUp, Building2, Shield, Users, Activity,
  Briefcase, ArrowUpRight, DollarSign, BellRing, ChevronRight,
  Filter, Download, Share2, Plus, MapPin, Globe, Mail, FileText, CheckCircle2, X
} from 'lucide-react';
import IsometricMap from './IsometricMap';
import './DirectorPortal.css';

const DirectorPortal = () => {
  const [stats, setStats] = useState(null);
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'societies' | 'sites'
  const [societies, setSocieties] = useState([]);
  const [sites, setSites] = useState([]);
  const [loading, setLoading] = useState(false);

  // Modals state
  const [showCreateSociety, setShowCreateSociety] = useState(false);
  const [societyForm, setSocietyForm] = useState({
    name: '',
    client_type: 'SOCIETY',
    address: '',
    billing_email: '',
    gstin: ''
  });

  const [showCreateSite, setShowCreateSite] = useState(false);
  const [siteForm, setSiteForm] = useState({
    society: '',
    name: '',
    latitude: '18.5204',
    longitude: '73.8567',
    geofence_radius_m: '100'
  });

  const [formMsg, setFormMsg] = useState({ type: '', text: '' });

  const fetchData = useCallback(async () => {
    try {
      const [statsRes, socRes, sitesRes] = await Promise.all([
        dashboardApi.stats(),
        societyApi.list(),
        societyApi.getSites()
      ]);
      setStats(statsRes.data);
      const socList = Array.isArray(socRes.data) ? socRes.data : (socRes.data?.results || []);
      setSocieties(socList);
      if (socList.length > 0 && !siteForm.society) {
        setSiteForm(f => ({ ...f, society: socList[0].id }));
      }
      const sitesList = Array.isArray(sitesRes.data) ? sitesRes.data : (sitesRes.data?.results || []);
      setSites(sitesList);
    } catch (err) {
      console.error("Failed to fetch director data", err);
    }
  }, [siteForm.society]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCreateSociety = async (e) => {
    e.preventDefault();
    setLoading(true);
    setFormMsg({ type: '', text: '' });
    try {
      await societyApi.create(societyForm);
      setFormMsg({ type: 'success', text: 'Client Society created successfully!' });
      setShowCreateSociety(false);
      setSocietyForm({ name: '', client_type: 'SOCIETY', address: '', billing_email: '', gstin: '' });
      await fetchData();
    } catch (err) {
      setFormMsg({ type: 'error', text: err.response?.data?.error || 'Failed to create society.' });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSite = async (e) => {
    e.preventDefault();
    setLoading(true);
    setFormMsg({ type: '', text: '' });
    try {
      await societyApi.createSite({
        society: siteForm.society,
        name: siteForm.name,
        latitude: parseFloat(siteForm.latitude),
        longitude: parseFloat(siteForm.longitude),
        geofence_radius_m: parseInt(siteForm.geofence_radius_m, 10)
      });
      setFormMsg({ type: 'success', text: 'Site created with active geofence!' });
      setShowCreateSite(false);
      setSiteForm(f => ({ ...f, name: '' }));
      await fetchData();
    } catch (err) {
      setFormMsg({ type: 'error', text: err.response?.data?.error || 'Failed to create site.' });
    } finally {
      setLoading(false);
    }
  };

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
            <p>Altus Managed Staffing Platform</p>
          </div>
        </div>
        
        {/* Top View Mode Tabs */}
        <div className="director-view-tabs glass-pill">
          <button 
            className={`view-tab ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            Overview
          </button>
          <button 
            className={`view-tab ${activeTab === 'societies' ? 'active' : ''}`}
            onClick={() => setActiveTab('societies')}
          >
            Societies ({societies.length})
          </button>
          <button 
            className={`view-tab ${activeTab === 'sites' ? 'active' : ''}`}
            onClick={() => setActiveTab('sites')}
          >
            Sites ({sites.length})
          </button>
        </div>
      </header>

      {formMsg.text && (
        <div className={`director-notification ${formMsg.type}`}>
          {formMsg.text}
        </div>
      )}

      {/* ── TAB 1: OVERVIEW ── */}
      {activeTab === 'overview' && (
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
                <h2>{stats?.total_revenue ? `₹${stats.total_revenue.toLocaleString()}` : '₹0'}</h2>
                <div className="hero-trend">
                  <ArrowUpRight size={18} />
                  <span>+12.4% vs last quarter</span>
                </div>
              </div>
              <div className="hero-glow"></div>
            </div>
          </motion.div>

          <motion.div variants={itemVariants} className="ed-card stat-card glass-card">
            <div className="stat-icon-wrap text-blue glow-blue"><Activity size={24} /></div>
            <div className="stat-details">
              <span className="stat-label">Total Requests</span>
              <span className="stat-value">{stats?.total_requests || 0}</span>
            </div>
          </motion.div>

          <motion.div variants={itemVariants} className="ed-card stat-card glass-card">
            <div className="stat-icon-wrap text-green glow-green"><DollarSign size={24} /></div>
            <div className="stat-details">
              <span className="stat-label">Client Societies</span>
              <span className="stat-value">{societies.length}</span>
            </div>
          </motion.div>

          {/* 3D Incident Map */}
          <motion.div variants={itemVariants} className="ed-card map-card glass-card" style={{ gridColumn: '1 / -1' }}>
            <div className="card-header">
              <h3><Building2 size={18} className="text-blue" style={{marginRight: '8px', display: 'inline'}} /> Property Command Map</h3>
            </div>
            <IsometricMap requests={[{ id: 99, service: 'Generator Failure', location: 'Tower B', status: 'Active' }]} />
          </motion.div>

          {/* Active Alerts */}
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
      )}

      {/* ── TAB 2: CLIENT SOCIETIES ── */}
      {activeTab === 'societies' && (
        <div className="director-management-section">
          <div className="section-toolbar">
            <div>
              <h2>Client Societies</h2>
              <p>Managed housing societies, hospitals, and office complexes</p>
            </div>
            <button className="btn-create-primary" onClick={() => setShowCreateSociety(true)}>
              <Plus size={18} />
              <span>New Client Society</span>
            </button>
          </div>

          <div className="societies-grid">
            {societies.map((soc) => (
              <motion.div key={soc.id} className="society-card glass-card" whileHover={{ y: -4 }}>
                <div className="society-card-top">
                  <div className="society-type-badge">{soc.client_type}</div>
                  <div className="member-count-badge">
                    <Users size={14} />
                    <span>{soc.member_count || 0} Members</span>
                  </div>
                </div>

                <h3>{soc.name}</h3>

                <div className="society-card-details">
                  <div className="detail-line">
                    <MapPin size={15} className="text-muted" />
                    <span>{soc.address || 'Address not registered'}</span>
                  </div>
                  {soc.billing_email && (
                    <div className="detail-line">
                      <Mail size={15} className="text-muted" />
                      <span>{soc.billing_email}</span>
                    </div>
                  )}
                  {soc.gstin && (
                    <div className="detail-line">
                      <FileText size={15} className="text-muted" />
                      <span>GST: {soc.gstin}</span>
                    </div>
                  )}
                </div>

                <div className="society-card-foot">
                  <span className="active-indicator">● Active Client</span>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* ── TAB 3: SITES & GEOFENCES ── */}
      {activeTab === 'sites' && (
        <div className="director-management-section">
          <div className="section-toolbar">
            <div>
              <h2>Client Sites & Geofences</h2>
              <p>Physical geofenced locations where workers clock-in</p>
            </div>
            <button className="btn-create-primary" onClick={() => setShowCreateSite(true)}>
              <Plus size={18} />
              <span>Add Geofenced Site</span>
            </button>
          </div>

          <div className="sites-grid">
            {sites.map((site) => (
              <motion.div key={site.id} className="site-card glass-card" whileHover={{ y: -4 }}>
                <div className="site-card-top">
                  <div className="site-society-badge">{site.society_name}</div>
                  <div className="geofence-radius-badge">
                    <Globe size={14} />
                    <span>{site.geofence_radius_m}m Radius</span>
                  </div>
                </div>

                <h3>{site.name}</h3>

                <div className="site-coords">
                  <div className="coord-box">
                    <span className="coord-label">Latitude</span>
                    <strong>{site.latitude}</strong>
                  </div>
                  <div className="coord-box">
                    <span className="coord-label">Longitude</span>
                    <strong>{site.longitude}</strong>
                  </div>
                </div>

                <div className="site-card-foot">
                  <span className="geofence-active-badge">
                    <CheckCircle2 size={14} color="#10b981" />
                    Geofence Enforcement Enabled
                  </span>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* ── CREATE SOCIETY MODAL ── */}
      <AnimatePresence>
        {showCreateSociety && (
          <div className="modal-backdrop" onClick={() => setShowCreateSociety(false)}>
            <motion.div 
              className="modal-box glass-card" 
              onClick={(e) => e.stopPropagation()}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
            >
              <div className="modal-head">
                <h3>Create New Client Society</h3>
                <button className="modal-close-btn" onClick={() => setShowCreateSociety(false)}><X size={20}/></button>
              </div>

              <form onSubmit={handleCreateSociety} className="director-form">
                <div className="form-group">
                  <label>Client Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Palm Heights Housing Society"
                    value={societyForm.name}
                    onChange={(e) => setSocietyForm({ ...societyForm, name: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label>Client Type</label>
                  <select
                    value={societyForm.client_type}
                    onChange={(e) => setSocietyForm({ ...societyForm, client_type: e.target.value })}
                  >
                    <option value="SOCIETY">Housing Society (Residential)</option>
                    <option value="HOSPITAL">Hospital / Healthcare</option>
                    <option value="OFFICE">Corporate Office / Commercial</option>
                  </select>
                </div>

                <div className="form-group">
                  <label>Full Address</label>
                  <textarea
                    rows={2}
                    required
                    placeholder="Plot 42, Sector 14, Pune"
                    value={societyForm.address}
                    onChange={(e) => setSocietyForm({ ...societyForm, address: e.target.value })}
                  />
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Billing Email</label>
                    <input
                      type="email"
                      placeholder="accounts@palmheights.com"
                      value={societyForm.billing_email}
                      onChange={(e) => setSocietyForm({ ...societyForm, billing_email: e.target.value })}
                    />
                  </div>

                  <div className="form-group">
                    <label>GSTIN (Optional)</label>
                    <input
                      type="text"
                      placeholder="27AAAAA0000A1Z5"
                      value={societyForm.gstin}
                      onChange={(e) => setSocietyForm({ ...societyForm, gstin: e.target.value })}
                    />
                  </div>
                </div>

                <div className="modal-foot">
                  <button type="button" className="btn-secondary" onClick={() => setShowCreateSociety(false)}>Cancel</button>
                  <button type="submit" className="btn-primary" disabled={loading}>
                    {loading ? 'Creating...' : 'Create Society'}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ── CREATE SITE MODAL ── */}
      <AnimatePresence>
        {showCreateSite && (
          <div className="modal-backdrop" onClick={() => setShowCreateSite(false)}>
            <motion.div 
              className="modal-box glass-card" 
              onClick={(e) => e.stopPropagation()}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
            >
              <div className="modal-head">
                <h3>Add Geofenced Site</h3>
                <button className="modal-close-btn" onClick={() => setShowCreateSite(false)}><X size={20}/></button>
              </div>

              <form onSubmit={handleCreateSite} className="director-form">
                <div className="form-group">
                  <label>Target Society</label>
                  <select
                    value={siteForm.society}
                    onChange={(e) => setSiteForm({ ...siteForm, society: e.target.value })}
                  >
                    {societies.map((s) => (
                      <option key={s.id} value={s.id}>{s.name} ({s.client_type})</option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label>Site / Gate Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Main Gate & Clubhouse"
                    value={siteForm.name}
                    onChange={(e) => setSiteForm({ ...siteForm, name: e.target.value })}
                  />
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Latitude</label>
                    <input
                      type="number"
                      step="any"
                      required
                      value={siteForm.latitude}
                      onChange={(e) => setSiteForm({ ...siteForm, latitude: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Longitude</label>
                    <input
                      type="number"
                      step="any"
                      required
                      value={siteForm.longitude}
                      onChange={(e) => setSiteForm({ ...siteForm, longitude: e.target.value })}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label>Geofence Radius (Meters)</label>
                  <input
                    type="number"
                    min="20"
                    max="5000"
                    value={siteForm.geofence_radius_m}
                    onChange={(e) => setSiteForm({ ...siteForm, geofence_radius_m: e.target.value })}
                  />
                </div>

                <div className="modal-foot">
                  <button type="button" className="btn-secondary" onClick={() => setShowCreateSite(false)}>Cancel</button>
                  <button type="submit" className="btn-primary" disabled={loading}>
                    {loading ? 'Saving Site...' : 'Save Site'}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default DirectorPortal;
