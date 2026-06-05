import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { dashboardApi } from '../utils/api';
import { 
  TrendingUp, TrendingDown, DollarSign, PieChart, 
  Wallet, FileSpreadsheet, Download, Activity, ArrowRight, Loader2
} from 'lucide-react';
import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';
import './AdminAnalytics.css';

const AdminAnalytics = () => {
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.1 } }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0 }
  };

  const [isGenerating, setIsGenerating] = React.useState(false);

  const generatePDF = async () => {
    setIsGenerating(true);
    const element = document.getElementById('report-content');
    
    try {
      const canvas = await html2canvas(element, { scale: 2, useCORS: true });
      const imgData = canvas.toDataURL('image/png');
      
      const pdf = new jsPDF('p', 'mm', 'a4');
      const pdfWidth = pdf.internal.pageSize.getWidth();
      const pdfHeight = (canvas.height * pdfWidth) / canvas.width;
      
      pdf.addImage(imgData, 'PNG', 0, 0, pdfWidth, pdfHeight);
      pdf.save('Altsan_PnL_Report.pdf');
    } catch (error) {
      console.error("PDF Generation failed", error);
      alert("Failed to generate PDF. Please try again.");
    } finally {
      setIsGenerating(false);
    }
  };

  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dashboardApi.stats().then(res => {
      setStats(res.data);
      setLoading(false);
    }).catch(err => {
      console.error(err);
      setLoading(false);
    });
  }, []);

  if (loading || !stats) {
    return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', background: '#0f172a' }}><Loader2 size={48} className="spinner text-indigo" /></div>;
  }

  // Derive P&L Data from real stats (Assuming 55% goes to workers)
  const grossRev = stats.total_revenue || 0;
  const expenses = grossRev * 0.55; 
  const netProfit = grossRev - expenses;
  const netMargin = grossRev > 0 ? ((netProfit / grossRev) * 100).toFixed(1) : 0;

  // Derive Monthly Chart from real trends
  // Assume avg ticket is ₹1500
  const monthlyData = stats.monthly_trend ? stats.monthly_trend.map(t => ({
    month: t.month,
    revenue: t.count * 1500,
    expense: (t.count * 1500) * 0.55
  })) : [];

  return (
    <div className="pl-analytics-container" id="report-content">
      <div className="pl-bg-glow"></div>
      
      <header className="pl-header">
        <div className="pl-header-left">
          <div className="pl-icon-box">
            <PieChart size={24} className="text-indigo" />
          </div>
          <div>
            <h1>Profit & Loss Statement</h1>
            <p>Financial deep dive & margins</p>
          </div>
        </div>
        <div className="pl-actions">
          <button className="pl-btn secondary">
            <FileSpreadsheet size={16} /> Export CSV
          </button>
          <button className="pl-btn primary" onClick={generatePDF} disabled={isGenerating}>
            {isGenerating ? <Loader2 size={16} className="spinner" /> : <Download size={16} />} 
            {isGenerating ? 'Generating...' : 'Download Report'}
          </button>
        </div>
      </header>

      <motion.div 
        className="pl-grid"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        {/* Top KPI Cards */}
        <motion.div variants={itemVariants} className="pl-card kpi-master">
          <div className="kpi-header">Gross Revenue</div>
          <div className="kpi-value">₹{grossRev.toLocaleString('en-IN')}</div>
          <div className="kpi-trend positive"><TrendingUp size={14} /> Based on {stats.resolved_requests} completed jobs</div>
        </motion.div>

        <motion.div variants={itemVariants} className="pl-card kpi-master">
          <div className="kpi-header">Total Expenses (Payouts)</div>
          <div className="kpi-value text-red">₹{expenses.toLocaleString('en-IN')}</div>
          <div className="kpi-trend negative"><TrendingDown size={14} /> 55% standard cut</div>
        </motion.div>

        <motion.div variants={itemVariants} className="pl-card kpi-master highlight-kpi">
          <div className="kpi-header text-white">Net Profit Margin</div>
          <div className="kpi-value text-white">{netMargin}%</div>
          <div className="kpi-trend text-green-light"><TrendingUp size={14} /> +2.1% Margin Growth</div>
          <div className="kpi-bg-accent"></div>
        </motion.div>

        {/* Dual Bar Chart: Rev vs Expense */}
        <motion.div variants={itemVariants} className="pl-card chart-section">
          <div className="card-top">
            <h3>Revenue vs. Expenses (H1)</h3>
            <div className="chart-legend">
              <span className="legend-item"><span className="dot rev-dot"></span> Income</span>
              <span className="legend-item"><span className="dot exp-dot"></span> Expense</span>
            </div>
          </div>
          <div className="dual-chart-container">
            {monthlyData.map((data, i) => (
              <div key={i} className="dual-bar-group">
                <div className="bars-wrapper">
                  {/* Revenue Bar */}
                  <motion.div 
                    className="bar-rev"
                    initial={{ height: 0 }}
                    animate={{ height: `${Math.max((data.revenue / 20000) * 100, 5)}%` }}
                    transition={{ duration: 1, delay: 0.1 * i }}
                  />
                  {/* Expense Bar */}
                  <motion.div 
                    className="bar-exp"
                    initial={{ height: 0 }}
                    animate={{ height: `${Math.max((data.expense / 20000) * 100, 5)}%` }}
                    transition={{ duration: 1, delay: 0.2 + (0.1 * i) }}
                  />
                </div>
                <span className="month-label">{data.month}</span>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Detailed P&L Breakdown Table */}
        <motion.div variants={itemVariants} className="pl-card breakdown-section">
          <div className="card-top">
            <h3>P&L Breakdown (June)</h3>
          </div>
          <div className="pl-table-wrapper">
            <table className="pl-table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th className="text-right">Amount (₹)</th>
                  <th className="text-right">% of Rev</th>
                </tr>
              </thead>
              <tbody>
                <tr className="row-income">
                  <td>Service Bookings (Gross)</td>
                  <td className="text-right font-bold">2,10,000</td>
                  <td className="text-right">100%</td>
                </tr>
                <tr className="row-expense">
                  <td>Worker Payouts (COGS)</td>
                  <td className="text-right">-1,15,500</td>
                  <td className="text-right">55%</td>
                </tr>
                <tr className="row-expense">
                  <td>Platform Hosting & API</td>
                  <td className="text-right">-4,200</td>
                  <td className="text-right">2%</td>
                </tr>
                <tr className="row-expense">
                  <td>Marketing & Ads</td>
                  <td className="text-right">-3,150</td>
                  <td className="text-right">1.5%</td>
                </tr>
                <tr className="row-expense">
                  <td>Taxes & Compliance</td>
                  <td className="text-right">-2,150</td>
                  <td className="text-right">1%</td>
                </tr>
                <tr className="row-net">
                  <td><strong>Net Operating Profit</strong></td>
                  <td className="text-right font-bold text-green">85,000</td>
                  <td className="text-right font-bold text-green">40.5%</td>
                </tr>
              </tbody>
            </table>
          </div>
        </motion.div>

        {/* Expense Distribution Donut Alternative */}
        <motion.div variants={itemVariants} className="pl-card expense-dist">
          <div className="card-top">
            <h3>Expense Distribution</h3>
          </div>
          <div className="dist-list">
            <div className="dist-item">
              <div className="dist-icon bg-red-light text-red"><Wallet size={18} /></div>
              <div className="dist-info">
                <h4>Worker Payouts</h4>
                <div className="progress-bar"><div className="fill bg-red" style={{width: '85%'}}></div></div>
              </div>
              <div className="dist-val">85%</div>
            </div>
            <div className="dist-item">
              <div className="dist-icon bg-blue-light text-blue"><Activity size={18} /></div>
              <div className="dist-info">
                <h4>Operations</h4>
                <div className="progress-bar"><div className="fill bg-blue" style={{width: '10%'}}></div></div>
              </div>
              <div className="dist-val">10%</div>
            </div>
            <div className="dist-item">
              <div className="dist-icon bg-orange-light text-orange"><TrendingUp size={18} /></div>
              <div className="dist-info">
                <h4>Marketing</h4>
                <div className="progress-bar"><div className="fill bg-orange" style={{width: '5%'}}></div></div>
              </div>
              <div className="dist-val">5%</div>
            </div>
          </div>
        </motion.div>

      </motion.div>
    </div>
  );
};

export default AdminAnalytics;
