import React from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, BarChart3, Building2, MoreVertical, Shield } from 'lucide-react';
import './Dashboard.css';

const DirectorPortal = () => {
  // Mock data for the bar charts
  const analyticsData = [
    { month: 'Jan', val: 40 },
    { month: 'Feb', val: 70 },
    { month: 'Mar', val: 45 },
    { month: 'Apr', val: 90 },
    { month: 'May', val: 65 },
    { month: 'Jun', val: 85 }
  ];

  const topAgencies = [
    { name: 'Elite Cleaners Corp', rating: 4.9, cost: '₹2,400', color: 'var(--accent-green)' },
    { name: 'Society Shine Plumbers', rating: 4.7, cost: '₹1,850', color: 'var(--accent-orange)' },
    { name: 'City Secure Guards', rating: 4.8, cost: '₹3,200', color: 'var(--accent-blue)' }
  ];

  return (
    <div className="mobile-dashboard">
      
      {/* Dark Hero Card for Total Revenue */}
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="hero-card shadow-glass"
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
           <div style={{ background: 'rgba(255,255,255,0.1)', padding: '6px 12px', borderRadius: '100px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Building2 size={14}/>
              <span>Society Management Overview</span>
           </div>
           <MoreVertical size={20} style={{ color: 'rgba(255,255,255,0.6)' }} />
        </div>

        <div style={{ textAlign: 'center', marginBottom: '16px' }}>
           <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: '14px', marginBottom: '4px' }}>Total Society Budget (YTD)</p>
           <h2 style={{ fontSize: '42px', fontWeight: '800', letterSpacing: '-1px' }}>₹1,240,500</h2>
           
           <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '4px', color: 'var(--accent-green)', marginTop: '8px' }}>
              <TrendingUp size={16} />
              <span style={{ fontSize: '14px', fontWeight: '700' }}>+12.4% vs last quarter</span>
           </div>
        </div>
      </motion.div>

      {/* Financial Analytics Chart Card */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="white-card"
        style={{ padding: '24px' }}
      >
         <h3 style={{ fontSize: '18px', fontWeight: '700', marginBottom: '4px' }}>Financial Analytics</h3>
         <p style={{ color: 'var(--text-soft)', fontSize: '13px', marginBottom: '24px' }}>Average net profit per month <span style={{fontWeight: '700', color: 'var(--text-main)'}}>₹42,000</span></p>
         
         <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', height: '140px', paddingBottom: '16px', borderBottom: '1px solid rgba(0,0,0,0.05)', marginBottom: '12px' }}>
           {analyticsData.map((data, i) => (
              <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                {/* Thick vertical bar per reference */}
                <motion.div 
                  initial={{ height: 0 }}
                  animate={{ height: `${data.val}%` }}
                  transition={{ duration: 1, delay: 0.2 + (i * 0.1), type: 'spring' }}
                  style={{ width: '28px', background: 'var(--primary)', borderRadius: '100px', minHeight: '10px' }} 
                />
                <span style={{ fontSize: '11px', fontWeight: '600', color: 'var(--text-muted)' }}>{data.month}</span>
              </div>
           ))}
         </div>
      </motion.div>

      <div className="section-title">
        <span>Top Performing Agencies</span>
      </div>
      
      {/* List format similar to goals in reference */}
      <div className="amenities-list">
        {topAgencies.map((agency, idx) => (
           <motion.div 
             key={idx}
             initial={{ opacity: 0, x: -20 }}
             animate={{ opacity: 1, x: 0 }}
             transition={{ delay: 0.3 + (idx * 0.1) }}
             className="white-card amenity-card"
           >
             <div className="amenity-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                   <div style={{ padding: '10px', background: 'rgba(0,0,0,0.03)', borderRadius: '12px', color: agency.color }}>
                     <Shield size={20} />
                   </div>
                   <div>
                     <h3 style={{ fontSize: '15px', fontWeight: '700' }}>{agency.name}</h3>
                     <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Rating: ⭐ {agency.rating}</p>
                   </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                   <span style={{ display: 'block', fontSize: '14px', fontWeight: '700' }}>{agency.cost}</span>
                   <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Paid Month</span>
                </div>
             </div>
           </motion.div>
        ))}
      </div>

    </div>
  );
};

export default DirectorPortal;
