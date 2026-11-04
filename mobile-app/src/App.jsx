import React, { useState, useEffect } from 'react';
import AttendanceScreen from './screens/AttendanceScreen.jsx';
import JobsScreen from './screens/JobsScreen.jsx';
import altsanLogo from './assets/altsan-logo.png';
import { SecureStorage } from './services/secureStorage.js';
import {
  API_BASE,
  subscribeAuthEvents,
  subscribeClockDrift,
  getIsClockDrifted,
} from './services/apiClient.js';
import {
  getPendingCount,
  hasPendingItems,
  flushQueue,
  subscribeQueueEvents,
} from './services/offlineQueue.js';
import { getDeviceId } from './utils/uuid.js';
import { useI18n } from './context/I18nContext.jsx';

function App() {
  const { locale, setLocale, t, getFriendlyError } = useI18n();

  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [initLoading, setInitLoading] = useState(true);

  const [activeTab, setActiveTab] = useState('attendance');
  const [pendingSyncCount, setPendingSyncCount] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);
  const [clockDriftAlert, setClockDriftAlert] = useState(getIsClockDrifted());

  // Phone + OTP State
  const [phone, setPhone] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState('');
  const [loginMessage, setLoginMessage] = useState('');

  // 1. Initial SecureStorage hydration
  useEffect(() => {
    (async () => {
      try {
        const storedToken = await SecureStorage.get('access_token');
        const storedUser = await SecureStorage.get('worker_profile');
        if (storedToken && storedUser) {
          setToken(storedToken);
          setUser(JSON.parse(storedUser));
        }
      } catch (err) {
        console.warn('[App] Token hydration error:', err);
      } finally {
        setInitLoading(false);
      }
    })();
  }, []);

  // 2. Auth revocation & Clock drift listeners
  useEffect(() => {
    const unsubAuth = subscribeAuthEvents((event) => {
      if (event.type === 'LOGOUT') {
        setToken(null);
        setUser(null);
      }
    });

    const unsubClock = subscribeClockDrift(({ isClockDrifted }) => {
      setClockDriftAlert(isClockDrifted);
    });

    return () => {
      unsubAuth();
      unsubClock();
    };
  }, []);

  // 3. Queue Pending Items Badge
  useEffect(() => {
    if (!user?.id) return;

    getPendingCount(user.id).then(setPendingSyncCount);
    const unsubQueue = subscribeQueueEvents(({ workerId, pendingCount }) => {
      if (workerId === user.id) {
        setPendingSyncCount(pendingCount);
      }
    });

    return () => unsubQueue();
  }, [user?.id]);

  // 4. OTP cooldown ticker
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setInterval(() => {
      setCooldown((c) => Math.max(0, c - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

  // ── Manual Sync Action ─────────────────────────────────────────
  const handleManualSync = async () => {
    if (!user?.id || isSyncing) return;
    setIsSyncing(true);
    try {
      await flushQueue(user.id);
      const count = await getPendingCount(user.id);
      setPendingSyncCount(count);
    } finally {
      setIsSyncing(false);
    }
  };

  // ── Request OTP ────────────────────────────────────────────────
  const handleRequestOtp = async (e) => {
    e?.preventDefault();
    setLoginLoading(true);
    setLoginError('');
    setLoginMessage('');

    const trimmedPhone = phone.trim();
    if (!trimmedPhone || trimmedPhone.replace(/\D/g, '').length < 10) {
      setLoginError(t('login_phone_label'));
      setLoginLoading(false);
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/auth/otp/request/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone: trimmedPhone,
          device_id: getDeviceId(),
        }),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        if (res.status === 429) {
          if (data.cooldown_seconds) setCooldown(data.cooldown_seconds);
          throw new Error(data.error || t('error_rate_limited', { seconds: 30 }));
        }
        throw new Error(data.error || 'Failed to dispatch verification code.');
      }

      setOtpSent(true);
      setCooldown(data.cooldown_seconds || 30);
      setLoginMessage(data.message || 'OTP sent successfully.');
    } catch (err) {
      setLoginError(getFriendlyError(err));
    } finally {
      setLoginLoading(false);
    }
  };

  // ── Verify OTP / Code ──────────────────────────────────────────
  const handleVerifyOtp = async (e) => {
    e?.preventDefault();
    setLoginLoading(true);
    setLoginError('');

    const trimmedCode = otpCode.trim();
    if (!trimmedCode || trimmedCode.length < 4) {
      setLoginError(t('login_otp_label'));
      setLoginLoading(false);
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/auth/otp/verify/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone: phone.trim(),
          code: trimmedCode,
          device_id: getDeviceId(),
        }),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.error || 'Invalid or expired verification code.');
      }

      // Store credentials into Keystore SecureStorage (Amendment 4)
      await SecureStorage.set('access_token', data.access);
      if (data.refresh) {
        await SecureStorage.set('refresh_token', data.refresh);
      }

      const workerProfile = {
        id: String(data.worker_id),
        worker_id: String(data.worker_id),
        username: data.username,
        verification_status: data.verification_status,
      };

      await SecureStorage.set('worker_profile', JSON.stringify(workerProfile));
      setUser(workerProfile);
      setToken(data.access);
    } catch (err) {
      setLoginError(getFriendlyError(err));
    } finally {
      setLoginLoading(false);
    }
  };

  // ── Safe Logout with Pending Items Warning (Amendment 3) ────────
  const handleLogout = async () => {
    if (user?.id) {
      const hasPending = await hasPendingItems(user.id);
      if (hasPending) {
        const count = await getPendingCount(user.id);
        const proceed = window.confirm(t('login_logout_confirm', { count }));
        if (!proceed) return;
      }
    }

    await SecureStorage.clearTokens();
    setToken(null);
    setUser(null);
    setOtpSent(false);
    setOtpCode('');
  };

  const toggleLanguage = () => {
    setLocale(locale === 'hi' ? 'en' : 'hi');
  };

  if (initLoading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#070a13', color: '#fff' }}>
        <p>Loading Altsan Worker…</p>
      </div>
    );
  }

  // ── Login Screen ───────────────────────────────────────────────
  if (!token) {
    return (
      <div
        className="mobile-login-container"
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          padding: '24px',
          backgroundColor: '#070a13',
          color: '#ffffff',
        }}
      >
        <div
          style={{
            width: '100%',
            maxWidth: '380px',
            background: '#10172a',
            padding: '32px 24px',
            borderRadius: '24px',
            boxShadow: '0 20px 40px rgba(0,0,0,0.7)',
            border: '1px solid rgba(255,255,255,0.15)',
            textAlign: 'center',
          }}
        >
          {/* Header language toggle */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '12px' }}>
            <button type="button" className="lang-toggle-btn" onClick={toggleLanguage}>
              🌐 {locale === 'hi' ? 'English' : 'हिन्दी'}
            </button>
          </div>

          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '16px' }}>
            <img
              src={altsanLogo}
              alt="Altsan Logo"
              style={{
                height: '76px',
                width: 'auto',
                objectFit: 'contain',
                filter: 'drop-shadow(0 8px 16px rgba(0,0,0,0.5))',
              }}
            />
          </div>

          <h2 style={{ fontSize: '24px', fontWeight: 800, marginBottom: '4px' }}>
            {t('app_name')}
          </h2>
          <p style={{ color: '#cbd5e1', fontSize: '13px', marginBottom: '24px' }}>
            {t('app_tagline')}
          </p>

          {loginError && (
            <div
              style={{
                background: 'rgba(239, 68, 68, 0.2)',
                color: '#fca5a5',
                padding: '12px',
                borderRadius: '12px',
                fontSize: '13px',
                marginBottom: '16px',
                border: '1px solid rgba(239, 68, 68, 0.4)',
                textAlign: 'left',
              }}
            >
              ⚠️ {loginError}
            </div>
          )}

          {loginMessage && (
            <div
              style={{
                background: 'rgba(16, 185, 129, 0.2)',
                color: '#86efac',
                padding: '12px',
                borderRadius: '12px',
                fontSize: '13px',
                marginBottom: '16px',
                border: '1px solid rgba(16, 185, 129, 0.4)',
                textAlign: 'left',
              }}
            >
              ℹ️ {loginMessage}
            </div>
          )}

          <form
            onSubmit={otpSent ? handleVerifyOtp : handleRequestOtp}
            style={{ display: 'flex', flexDirection: 'column', gap: '16px', textAlign: 'left' }}
          >
            <div>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#cbd5e1', marginBottom: '6px' }}>
                {t('login_phone_label')}
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type="tel"
                  placeholder={t('login_phone_placeholder')}
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  disabled={otpSent}
                  required
                  style={{
                    width: '100%',
                    padding: '14px 16px',
                    borderRadius: '12px',
                    background: otpSent ? '#0f172a' : '#17223b',
                    border: '1px solid rgba(255,255,255,0.2)',
                    color: 'white',
                    fontSize: '16px',
                    outline: 'none',
                  }}
                />
                {otpSent && (
                  <button
                    type="button"
                    onClick={() => {
                      setOtpSent(false);
                      setOtpCode('');
                    }}
                    style={{
                      position: 'absolute',
                      right: '12px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'transparent',
                      color: '#60a5fa',
                      border: 'none',
                      fontSize: '12px',
                      cursor: 'pointer',
                      fontWeight: 700,
                    }}
                  >
                    बदलें / Change
                  </button>
                )}
              </div>
            </div>

            {otpSent && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <label style={{ fontSize: '13px', fontWeight: 700, color: '#cbd5e1' }}>
                    {t('login_otp_label')}
                  </label>
                  <button
                    type="button"
                    disabled={cooldown > 0 || loginLoading}
                    onClick={handleRequestOtp}
                    style={{
                      background: 'transparent',
                      color: cooldown > 0 ? '#64748b' : '#38bdf8',
                      border: 'none',
                      fontSize: '12px',
                      cursor: cooldown > 0 ? 'default' : 'pointer',
                      fontWeight: 700,
                    }}
                  >
                    {cooldown > 0 ? t('login_resend_cooldown', { seconds: cooldown }) : t('login_resend_otp')}
                  </button>
                </div>
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  placeholder="••••••"
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value)}
                  required
                  autoFocus
                  style={{
                    width: '100%',
                    padding: '14px 16px',
                    borderRadius: '12px',
                    background: '#17223b',
                    border: '2px solid #3b82f6',
                    color: 'white',
                    fontSize: '22px',
                    letterSpacing: '8px',
                    textAlign: 'center',
                    outline: 'none',
                  }}
                />
              </div>
            )}

            <button
              type="submit"
              disabled={loginLoading}
              style={{
                marginTop: '8px',
                padding: '16px',
                borderRadius: '14px',
                background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
                color: 'white',
                border: 'none',
                fontSize: '16px',
                fontWeight: 800,
                cursor: 'pointer',
                minHeight: '52px',
              }}
            >
              {loginLoading ? 'प्रतीक्षा करें…' : otpSent ? t('login_verify_button') : t('login_send_otp')}
            </button>
          </form>
        </div>
      </div>
    );
  }

  // ── Authenticated App Shell ────────────────────────────────────
  return (
    <div className="mobile-app-wrapper" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Clock Drift Alert Banner */}
      {clockDriftAlert && (
        <div
          style={{
            background: '#b45309',
            color: '#fff',
            padding: '10px 16px',
            fontSize: '12px',
            fontWeight: 700,
            textAlign: 'center',
          }}
        >
          ⚠️ {t('clock_drift_warning')}
        </div>
      )}

      {/* Persistent Queue Sync Indicator Banner */}
      {pendingSyncCount > 0 && (
        <div className="sync-banner">
          <span>⏳ {t('sync_pending_banner', { count: pendingSyncCount })}</span>
          <button type="button" onClick={handleManualSync} disabled={isSyncing}>
            {isSyncing ? t('sync_in_progress') : t('sync_button')}
          </button>
        </div>
      )}

      {/* Active Screen */}
      {activeTab === 'attendance' && (
        <AttendanceScreen
          worker={user}
          onTabChange={setActiveTab}
          onLanguageToggle={toggleLanguage}
          locale={locale}
        />
      )}

      {activeTab === 'jobs' && (
        <JobsScreen
          worker={user}
          onTabChange={setActiveTab}
          onLanguageToggle={toggleLanguage}
          locale={locale}
        />
      )}

      {activeTab === 'earnings' && (
        <div style={{ padding: '32px 20px', textAlign: 'center', color: '#f8fafc' }}>
          <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
            <h2>{t('nav_earnings')}</h2>
            <button
              onClick={handleLogout}
              style={{
                background: 'rgba(239, 68, 68, 0.2)',
                color: '#f87171',
                border: '1px solid rgba(239, 68, 68, 0.4)',
                padding: '8px 14px',
                borderRadius: '8px',
                fontSize: '13px',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              {t('login_logout')}
            </button>
          </header>

          <div
            style={{
              background: '#10172a',
              borderRadius: '20px',
              padding: '24px 20px',
              border: '1px solid rgba(255,255,255,0.12)',
              marginBottom: '20px',
            }}
          >
            <p style={{ color: '#cbd5e1', fontSize: '14px', marginBottom: '8px' }}>Verified Balance</p>
            <h1 style={{ fontSize: '36px', fontWeight: 800, color: '#38bdf8' }}>₹350.00</h1>
            <p style={{ fontSize: '13px', color: '#10b981', marginTop: '8px' }}>● 100% Payout Reliability</p>
          </div>

          <nav className="mobile-tab-bar">
            <div className="tab-item" onClick={() => setActiveTab('attendance')}>
              <div className="tab-icon">🕒</div>
              <span>{t('nav_attendance')}</span>
            </div>
            <div className="tab-item" onClick={() => setActiveTab('jobs')}>
              <div className="tab-icon">💼</div>
              <span>{t('nav_jobs')}</span>
            </div>
            <div className="tab-item active" onClick={() => setActiveTab('earnings')}>
              <div className="tab-icon">💰</div>
              <span>{t('nav_earnings')}</span>
            </div>
          </nav>
        </div>
      )}
    </div>
  );
}

export default App;
