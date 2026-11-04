import React, { useState, useEffect, useCallback } from 'react';
import altsanLogo from '../assets/altsan-logo.png';
import ReplacementBanner from '../components/ReplacementBanner.jsx';
import { apiClient } from '../services/apiClient.js';
import { useI18n } from '../context/I18nContext.jsx';
import './JobsScreen.css';

const JobsScreen = ({ worker, onTabChange, onLanguageToggle, locale }) => {
  const { t } = useI18n();
  const [schedule, setSchedule] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [toastMsg, setToastMsg] = useState(null);

  const fetchSchedule = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient('/roster/my-schedule/');
      if (!res.ok) throw new Error('Could not load shift roster');
      const data = await res.json();
      const list = Array.isArray(data) ? data : data.results || [];
      setSchedule(list);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSchedule();
  }, [fetchSchedule]);

  return (
    <div className="mobile-app-container">
      <header className="mobile-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <img src={altsanLogo} alt="Altsan" className="header-mini-logo" />
          <h1 style={{ fontSize: '18px', fontWeight: 800 }}>{t('nav_jobs')}</h1>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <button className="filter-icon" onClick={fetchSchedule} title="Refresh">
            🔄
          </button>
          <button type="button" className="lang-toggle-btn" onClick={onLanguageToggle}>
            🌐 {locale === 'hi' ? 'EN' : 'हिन्दी'}
          </button>
        </div>
      </header>

      {/* Replacement Offer Banner */}
      <ReplacementBanner
        worker={worker}
        onNotice={(msg, type) => {
          if (type === 'error') setError(msg);
          else {
            setToastMsg(msg);
            setTimeout(() => setToastMsg(null), 3500);
          }
        }}
        onScheduleUpdated={fetchSchedule}
      />

      {toastMsg && (
        <div
          style={{
            background: 'rgba(16, 185, 129, 0.2)',
            border: '1px solid #10b981',
            color: '#86efac',
            padding: '10px 16px',
            borderRadius: '12px',
            fontSize: '13px',
            fontWeight: 700,
            marginBottom: '16px',
          }}
        >
          {toastMsg}
        </div>
      )}

      <main className="jobs-main">
        {loading && (
          <div className="jobs-loading">
            <p>Syncing schedule…</p>
          </div>
        )}

        {error && (
          <div className="jobs-error">
            <p>⚠️ {error}</p>
            <button onClick={fetchSchedule}>Retry</button>
          </div>
        )}

        {/* ── Scheduled Roster Shifts ─────────────────────────── */}
        {!loading && (
          <div className="jobs-list animate-fade-in">
            {schedule.length === 0 ? (
              <p className="empty-state">{t('shift_card_no_shift')}</p>
            ) : (
              schedule.map((slot) => (
                <div key={slot.roster_entry_id} className="job-card ongoing">
                  <div className="job-card-header">
                    <span className="status-tag pulse">
                      {slot.status === 'PRESENT' ? '🟢 Live on Shift' : slot.status}
                    </span>
                    <span className="priority-tag">{slot.date}</span>
                  </div>
                  <h3>{slot.post_name}</h3>
                  <p className="facility-name">🏢 {slot.site_name} • {slot.society_name}</p>
                  <p className="job-location">
                    🕒 {slot.shift_name} ({new Date(slot.shift_start_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} – {new Date(slot.shift_end_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })})
                  </p>

                  <div className="job-actions">
                    <button
                      className="btn-full"
                      onClick={() => onTabChange?.('attendance')}
                    >
                      🕒 {t('shift_clock_in_btn')} & {t('tasks_title')}
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </main>

      <nav className="mobile-tab-bar">
        <div className="tab-item" onClick={() => onTabChange?.('attendance')}>
          <div className="tab-icon">🕒</div>
          <span>{t('nav_attendance')}</span>
        </div>
        <div className="tab-item active" onClick={() => onTabChange?.('jobs')}>
          <div className="tab-icon">💼</div>
          <span>{t('nav_jobs')}</span>
        </div>
        <div className="tab-item" onClick={() => onTabChange?.('earnings')}>
          <div className="tab-icon">💰</div>
          <span>{t('nav_earnings')}</span>
        </div>
      </nav>
    </div>
  );
};

export default JobsScreen;
