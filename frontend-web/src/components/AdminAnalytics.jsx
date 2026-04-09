import React from 'react';
import './AdminAnalytics.css';

const AdminAnalytics = () => {
  return (
    <div className="analytics-container">
      <header className="analytics-header">
        <h1>Platform Analytics</h1>
        <div className="date-filter">
          <button className="active">Last 30 Days</button>
          <button>Last 90 Days</button>
          <button>This Year</button>
        </div>
      </header>

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <span className="kpi-label">Gross Revenue</span>
          <h2 className="kpi-value">$42,850.00</h2>
          <span className="kpi-trend positive">↑ 12% vs last month</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-label">Active Bookings</span>
          <h2 className="kpi-value">158</h2>
          <span className="kpi-trend positive">↑ 5% vs last month</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-label">Worker Fulfillment</span>
          <h2 className="kpi-value">94.2%</h2>
          <span className="kpi-trend negative">↓ 1.5% vs last month</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-label">Open Complaints</span>
          <h2 className="kpi-value">4</h2>
          <span className="kpi-trend positive">Stable</span>
        </div>
      </div>

      <div className="analytics-content">
        <section className="chart-placeholder section-main">
          <div className="section-header">
            <h3>Revenue Growth</h3>
            <span className="legend">Monthly Breakdown</span>
          </div>
          <div className="mock-chart">
            {/* Visual representation using divs to simulate bars */}
            <div className="bar" style={{ height: '40%' }}><span>Jan</span></div>
            <div className="bar" style={{ height: '55%' }}><span>Feb</span></div>
            <div className="bar" style={{ height: '75%' }}><span>Mar</span></div>
            <div className="bar active" style={{ height: '90%' }}><span>Apr</span></div>
          </div>
        </section>

        <section className="section-side">
          <h3>Top Service Categories</h3>
          <ul className="category-rank">
            <li>
              <div className="rank-info">
                <strong>Housekeeping</strong>
                <span>42% of revenue</span>
              </div>
              <div className="progress-mini"><div style={{ width: '85%' }}></div></div>
            </li>
            <li>
              <div className="rank-info">
                <strong>Security</strong>
                <span>28% of revenue</span>
              </div>
              <div className="progress-mini"><div style={{ width: '60%' }}></div></div>
            </li>
            <li>
              <div className="rank-info">
                <strong>Electrician</strong>
                <span>15% of revenue</span>
              </div>
              <div className="progress-mini"><div style={{ width: '40%' }}></div></div>
            </li>
          </ul>
        </section>
      </div>

      <section className="recent-activity section-full">
        <h3>Recent Operations Activity</h3>
        <table className="analytics-table">
          <thead>
            <tr>
              <th>Client</th>
              <th>Service</th>
              <th>Worker</th>
              <th>Status</th>
              <th>Revenue</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>City Care Hospital</td>
              <td>Housekeeping</td>
              <td>John Miller</td>
              <td><span className="status-pill success">Paid</span></td>
              <td>$450.00</td>
            </tr>
            <tr>
              <td>TechPark Tower B</td>
              <td>Security</td>
              <td>Arjun Sharma</td>
              <td><span className="status-pill pending">Invoiced</span></td>
              <td>$1,200.00</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  );
};

export default AdminAnalytics;
