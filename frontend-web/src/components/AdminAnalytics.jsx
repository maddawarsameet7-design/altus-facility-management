import React from 'react';
import { motion } from 'framer-motion';
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

  // Mock P&L Data
  const monthlyData = [
    { month: 'Jan', revenue: 120, expense: 80 },
    { month: 'Feb', revenue: 145, expense: 90 },
    { month: 'Mar', revenue: 130, expense: 85 },
    { month: 'Apr', revenue: 170, expense: 100 },
    { month: 'May', revenue: 190, expense: 110 },
    { month: 'Jun', revenue: 210, expense: 125 }
  ];

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
          <div className="kpi-value">₹12,45,000</div>
          <div className="kpi-trend positive"><TrendingUp size={14} /> +18.2% YTD</div>
        </motion.div>

        <motion.div variants={itemVariants} className="pl-card kpi-master">
          <div className="kpi-header">Total Expenses (Payouts)</div>
          <div className="kpi-value text-red">₹8,10,200</div>
          <div className="kpi-trend negative"><TrendingDown size={14} /> +4.5% YTD</div>
        </motion.div>

        <motion.div variants={itemVariants} className="pl-card kpi-master highlight-kpi">
          <div className="kpi-header text-white">Net Profit Margin</div>
          <div className="kpi-value text-white">34.9%</div>
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
                    animate={{ height: `${(data.revenue / 250) * 100}%` }}
                    transition={{ duration: 1, delay: 0.1 * i }}
                  />
                  {/* Expense Bar */}
                  <motion.div 
                    className="bar-exp"
                    initial={{ height: 0 }}
                    animate={{ height: `${(data.expense / 250) * 100}%` }}
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
