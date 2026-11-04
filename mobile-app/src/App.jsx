import React, { useState, useEffect } from 'react';
import AttendanceScreen from './screens/AttendanceScreen.jsx';
import JobsScreen from './screens/JobsScreen.jsx';
import altsanLogo from './assets/altsan-logo.png';
import { getDeviceId } from './utils/uuid.js';

const resolveApiBase = () => {
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_URL) {
    return import.meta.env.VITE_API_URL.replace(/\/+$/, '');
  }
  return 'https://api.altsan.com/api';
};

const API_BASE = resolveApiBase();

function App() {
  const [token, setToken] = useState(() => localStorage.getItem('altsan_token') || localStorage.getItem('access_token') || '');
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('altsan_user_data') || 'null');
    } catch {
      return null;
    }
  });

  const [activeTab, setActiveTab] = useState('attendance');
  const [selectedAssignmentId, setSelectedAssignmentId] = useState(null);

  // Login Mode: 'otp' (field staff) vs 'password' (fallback/supervisor)
  const [loginMode, setLoginMode] = useState('otp');

  // Phone + OTP State
  const [phone, setPhone] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [deviceNotice, setDeviceNotice] = useState(null);

  // Password fallback state
  const [username, setUsername] = useState('worker');
  const [password, setPassword] = useState('altus123');

  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState('');
  const [loginMessage, setLoginMessage] = useState('');

  // OTP cooldown ticker
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setInterval(() => {
      setCooldown((c) => Math.max(0, c - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

  // Validate or fetch profile
  useEffect(() => {
    if (!token) return;
    fetch(`${API_BASE}/user/me/`, {
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    })
      .then((res) => {
        if (!res.ok) throw new Error('Session expired');
        return res.json();
      })
      .then((data) => {
        setUser(data);
        localStorage.setItem('altsan_user_data', JSON.stringify(data));
      })
      .catch(() => {
        handleLogout();
      });
  }, [token]);

  // ── OTP Request (Send Code) ───────────────────────────────────
  const handleRequestOtp = async (e) => {
    e?.preventDefault();
    setLoginLoading(true);
    setLoginError('');
    setLoginMessage('');

    const trimmedPhone = phone.trim();
    if (!trimmedPhone || trimmedPhone.replace(/\D/g, '').length < 10) {
      setLoginError('Please enter a valid 10-digit mobile number.');
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

      const data = await res.json();

      if (!res.ok) {
        if (res.status === 429) {
          if (data.cooldown_seconds) {
            setCooldown(data.cooldown_seconds);
          }
          throw new Error(data.error || 'Please wait before requesting a new code.');
        }
        throw new Error(data.error || 'Could not send verification code.');
      }

      setOtpSent(true);
      setCooldown(data.cooldown_seconds || 30);
      setLoginMessage(data.message || 'Verification code sent via SMS.');
    } catch (err) {
      setLoginError(err.message);
    } finally {
      setLoginLoading(false);
    }
  };

  // ── OTP Verify (Submit Code) ──────────────────────────────────
  const handleVerifyOtp = async (e) => {
    e?.preventDefault();
    setLoginLoading(true);
    setLoginError('');

    const trimmedCode = otpCode.trim();
    if (!trimmedCode || trimmedCode.length < 4) {
      setLoginError('Please enter the 6-digit verification code.');
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

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || 'Invalid or expired verification code.');
      }

      const accessToken = data.access;
      const refreshToken = data.refresh;

      localStorage.setItem('altsan_token', accessToken);
      localStorage.setItem('access_token', accessToken);
      if (refreshToken) {
        localStorage.setItem('refresh_token', refreshToken);
      }

      const workerData = {
        id: data.worker_id,
        worker_id: data.worker_id,
        username: data.username,
        role: 'WORKER',
        verification_status: data.verification_status,
      };

      localStorage.setItem('altsan_user_data', JSON.stringify(workerData));
      setUser(workerData);
      setToken(accessToken);

      if (data.new_device_detected && !data.new_device_approved) {
        setDeviceNotice('New device detected. Verification pending supervisor confirmation.');
      }
    } catch (err) {
      setLoginError(err.message);
    } finally {
      setLoginLoading(false);
    }
  };

  // ── Password Login Fallback ───────────────────────────────────
  const handlePasswordLogin = async (e) => {
    e?.preventDefault();
    setLoginLoading(true);
    setLoginError('');
    try {
      const res = await fetch(`${API_BASE}/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.error || 'Authentication failed');
      }

      const accessToken = data.access;
      localStorage.setItem('altsan_token', accessToken);
      localStorage.setItem('access_token', accessToken);
      if (data.refresh) {
        localStorage.setItem('refresh_token', data.refresh);
      }
      setToken(accessToken);
    } catch (err) {
      setLoginError(err.message);
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('altsan_token');
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('altsan_user_data');
    setToken('');
    setUser(null);
    setOtpSent(false);
    setOtpCode('');
  };

  const handleTabChange = (tab, assignmentId = null) => {
    setActiveTab(tab);
    if (assignmentId) {
      setSelectedAssignmentId(assignmentId);
    }
  };

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
          backgroundColor: '#0b0f19',
          color: '#f8fafc',
        }}
      >
        <div
          style={{
            width: '100%',
            maxWidth: '380px',
            background: 'rgba(19, 27, 46, 0.95)',
            padding: '32px 24px',
            borderRadius: '24px',
            boxShadow: '0 20px 40px rgba(0,0,0,0.6)',
            border: '1px solid rgba(255,255,255,0.12)',
            textAlign: 'center',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '16px' }}>
            <img
              src={altsanLogo}
              alt="Altsan Logo"
              style={{
                height: '80px',
                width: 'auto',
                maxWidth: '100%',
                objectFit: 'contain',
                filter: 'drop-shadow(0 12px 24px rgba(0,0,0,0.5))',
              }}
            />
          </div>
          <h2 style={{ fontSize: '24px', fontWeight: 800, marginBottom: '6px' }}>Altus Worker</h2>
          <p style={{ color: '#94a3b8', fontSize: '14px', marginBottom: '20px' }}>Field Terminal & Roster Operations</p>

          {/* Login Mode Toggle */}
          <div
            style={{
              display: 'flex',
              background: '#0b0f19',
              borderRadius: '12px',
              padding: '4px',
              marginBottom: '20px',
              border: '1px solid rgba(255,255,255,0.08)',
            }}
          >
            <button
              type="button"
              onClick={() => {
                setLoginMode('otp');
                setLoginError('');
              }}
              style={{
                flex: 1,
                padding: '8px 12px',
                borderRadius: '8px',
                background: loginMode === 'otp' ? '#3b82f6' : 'transparent',
                color: loginMode === 'otp' ? '#fff' : '#94a3b8',
                border: 'none',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              📱 Mobile OTP
            </button>
            <button
              type="button"
              onClick={() => {
                setLoginMode('password');
                setLoginError('');
              }}
              style={{
                flex: 1,
                padding: '8px 12px',
                borderRadius: '8px',
                background: loginMode === 'password' ? '#3b82f6' : 'transparent',
                color: loginMode === 'password' ? '#fff' : '#94a3b8',
                border: 'none',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              🔑 Password
            </button>
          </div>

          {loginError && (
            <div
              style={{
                background: 'rgba(239, 68, 68, 0.15)',
                color: '#fca5a5',
                padding: '12px',
                borderRadius: '12px',
                fontSize: '13px',
                marginBottom: '16px',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                textAlign: 'left',
              }}
            >
              ⚠️ {loginError}
            </div>
          )}

          {loginMessage && (
            <div
              style={{
                background: 'rgba(16, 185, 129, 0.15)',
                color: '#86efac',
                padding: '12px',
                borderRadius: '12px',
                fontSize: '13px',
                marginBottom: '16px',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                textAlign: 'left',
              }}
            >
              ℹ️ {loginMessage}
            </div>
          )}

          {/* OTP Mode Form */}
          {loginMode === 'otp' && (
            <form
              onSubmit={otpSent ? handleVerifyOtp : handleRequestOtp}
              style={{ display: 'flex', flexDirection: 'column', gap: '16px', textAlign: 'left' }}
            >
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#94a3b8', marginBottom: '6px' }}>
                  Registered Phone Number
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    type="tel"
                    placeholder="e.g. 9876543210"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    disabled={otpSent}
                    required
                    style={{
                      width: '100%',
                      padding: '14px 16px',
                      borderRadius: '12px',
                      background: otpSent ? '#0f172a' : '#1a253c',
                      border: '1px solid rgba(255,255,255,0.1)',
                      color: 'white',
                      fontSize: '15px',
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
                        fontWeight: 600,
                      }}
                    >
                      Change
                    </button>
                  )}
                </div>
              </div>

              {otpSent && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <label style={{ fontSize: '12px', fontWeight: 600, color: '#94a3b8' }}>
                      6-Digit SMS Code
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
                        fontWeight: 600,
                      }}
                    >
                      {cooldown > 0 ? `Resend (${cooldown}s)` : 'Resend Code'}
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
                      background: '#1a253c',
                      border: '1px solid #3b82f6',
                      color: 'white',
                      fontSize: '20px',
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
                  background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
                  color: 'white',
                  border: 'none',
                  fontSize: '16px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  boxShadow: '0 10px 20px -5px rgba(59, 130, 246, 0.4)',
                }}
              >
                {loginLoading
                  ? 'Processing…'
                  : otpSent
                  ? 'Verify & Enter Terminal →'
                  : 'Send Verification Code →'}
              </button>
            </form>
          )}

          {/* Password Mode Form */}
          {loginMode === 'password' && (
            <form onSubmit={handlePasswordLogin} style={{ display: 'flex', flexDirection: 'column', gap: '16px', textAlign: 'left' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#94a3b8', marginBottom: '6px' }}>
                  Technician Username
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  style={{
                    width: '100%',
                    padding: '14px 16px',
                    borderRadius: '12px',
                    background: '#1a253c',
                    border: '1px solid rgba(255,255,255,0.1)',
                    color: 'white',
                    fontSize: '15px',
                    outline: 'none',
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#94a3b8', marginBottom: '6px' }}>
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  style={{
                    width: '100%',
                    padding: '14px 16px',
                    borderRadius: '12px',
                    background: '#1a253c',
                    border: '1px solid rgba(255,255,255,0.1)',
                    color: 'white',
                    fontSize: '15px',
                    outline: 'none',
                  }}
                />
              </div>

              <button
                type="submit"
                disabled={loginLoading}
                style={{
                  marginTop: '8px',
                  padding: '16px',
                  borderRadius: '14px',
                  background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
                  color: 'white',
                  border: 'none',
                  fontSize: '16px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  boxShadow: '0 10px 20px -5px rgba(59, 130, 246, 0.4)',
                }}
              >
                {loginLoading ? 'Authenticating…' : 'Launch Terminal →'}
              </button>
            </form>
          )}

          <p style={{ marginTop: '20px', fontSize: '12px', color: '#64748b' }}>
            Production Gateway: <code>{API_BASE}</code>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="mobile-app-wrapper" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {deviceNotice && (
        <div
          style={{
            background: 'rgba(245, 158, 11, 0.15)',
            borderBottom: '1px solid rgba(245, 158, 11, 0.3)',
            color: '#fde68a',
            padding: '10px 16px',
            fontSize: '12px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span>⚠️ {deviceNotice}</span>
          <button
            onClick={() => setDeviceNotice(null)}
            style={{ background: 'none', border: 'none', color: '#fde68a', cursor: 'pointer', fontSize: '14px' }}
          >
            ✕
          </button>
        </div>
      )}

      {activeTab === 'attendance' && (
        <AttendanceScreen
          assignmentId={selectedAssignmentId}
          onTabChange={handleTabChange}
        />
      )}

      {activeTab === 'jobs' && (
        <JobsScreen
          onTabChange={handleTabChange}
          onSelectJob={(id) => handleTabChange('attendance', id)}
        />
      )}

      {activeTab === 'earnings' && (
        <div style={{ padding: '32px 20px', textAlign: 'center', color: '#f8fafc' }}>
          <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
            <h2>Shift & Payouts</h2>
            <button
              onClick={handleLogout}
              style={{
                background: 'rgba(239, 68, 68, 0.2)',
                color: '#f87171',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                padding: '6px 12px',
                borderRadius: '8px',
                fontSize: '12px',
                cursor: 'pointer',
              }}
            >
              Sign Out
            </button>
          </header>

          <div
            style={{
              background: '#131b2e',
              borderRadius: '20px',
              padding: '28px 20px',
              border: '1px solid rgba(255,255,255,0.08)',
              marginBottom: '20px',
            }}
          >
            <p style={{ color: '#94a3b8', fontSize: '14px', marginBottom: '8px' }}>Verified Balance</p>
            <h1 style={{ fontSize: '36px', fontWeight: 800, color: '#38bdf8' }}>₹350.00</h1>
            <p style={{ fontSize: '13px', color: '#10b981', marginTop: '8px' }}>● 100% Payout Reliability</p>
          </div>

          <div
            style={{
              background: '#131b2e',
              borderRadius: '20px',
              padding: '20px',
              textAlign: 'left',
              border: '1px solid rgba(255,255,255,0.08)',
            }}
          >
            <h3 style={{ fontSize: '16px', marginBottom: '12px' }}>Technician Profile</h3>
            <p style={{ color: '#94a3b8', fontSize: '14px', marginBottom: '6px' }}>
              <strong>Username:</strong> {user?.username || 'worker'}
            </p>
            <p style={{ color: '#94a3b8', fontSize: '14px', marginBottom: '6px' }}>
              <strong>Role:</strong> {user?.role || 'WORKER'}
            </p>
            <p style={{ color: '#94a3b8', fontSize: '14px' }}>
              <strong>Status:</strong> {user?.verification_status || 'Active & Verified'} ✅
            </p>
          </div>

          <nav className="mobile-tab-bar">
            <div className="tab-item" onClick={() => handleTabChange('home')}>
              <div className="tab-icon">🏠</div>
              <span>Home</span>
            </div>
            <div className="tab-item" onClick={() => handleTabChange('attendance')}>
              <div className="tab-icon">🕒</div>
              <span>Attendance</span>
            </div>
            <div className="tab-item" onClick={() => handleTabChange('jobs')}>
              <div className="tab-icon">💼</div>
              <span>Jobs</span>
            </div>
            <div className="tab-item active" onClick={() => handleTabChange('earnings')}>
              <div className="tab-icon">💰</div>
              <span>Earnings</span>
            </div>
          </nav>
        </div>
      )}

      {activeTab === 'home' && (
        <div style={{ padding: '32px 20px', color: '#f8fafc', textAlign: 'center' }}>
          <h2>Altus Worker Hub</h2>
          <p style={{ color: '#94a3b8', margin: '16px 0 24px' }}>Welcome back, {user?.username || 'Technician'}!</p>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px' }}>
            <div
              onClick={() => handleTabChange('attendance')}
              style={{
                background: '#131b2e',
                padding: '24px 16px',
                borderRadius: '16px',
                border: '1px solid rgba(255,255,255,0.08)',
                cursor: 'pointer',
              }}
            >
              <div style={{ fontSize: '32px', marginBottom: '8px' }}>🕒</div>
              <h4 style={{ fontSize: '15px' }}>Attendance</h4>
              <p style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>Roster & Shift</p>
            </div>

            <div
              onClick={() => handleTabChange('jobs')}
              style={{
                background: '#131b2e',
                padding: '24px 16px',
                borderRadius: '16px',
                border: '1px solid rgba(255,255,255,0.08)',
                cursor: 'pointer',
              }}
            >
              <div style={{ fontSize: '32px', marginBottom: '8px' }}>💼</div>
              <h4 style={{ fontSize: '15px' }}>Job Queue</h4>
              <p style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>Tasks & Offers</p>
            </div>
          </div>

          <button
            onClick={handleLogout}
            style={{
              background: '#1f2937',
              color: '#94a3b8',
              border: 'none',
              padding: '12px 24px',
              borderRadius: '12px',
              cursor: 'pointer',
            }}
          >
            Log Out
          </button>

          <nav className="mobile-tab-bar">
            <div className="tab-item active" onClick={() => handleTabChange('home')}>
              <div className="tab-icon">🏠</div>
              <span>Home</span>
            </div>
            <div className="tab-item" onClick={() => handleTabChange('attendance')}>
              <div className="tab-icon">🕒</div>
              <span>Attendance</span>
            </div>
            <div className="tab-item" onClick={() => handleTabChange('jobs')}>
              <div className="tab-icon">💼</div>
              <span>Jobs</span>
            </div>
            <div className="tab-item" onClick={() => handleTabChange('earnings')}>
              <div className="tab-icon">💰</div>
              <span>Earnings</span>
            </div>
          </nav>
        </div>
      )}
    </div>
  );
}

export default App;
