import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, ArrowRight, ScanFace } from 'lucide-react';
import { authApi, userApi } from '../utils/api';
import './Auth.css';

const LoginRegistration = ({ onLoginSuccess }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [isRegisterSuccess, setIsRegisterSuccess] = useState(false);
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    role: 'MEMBER'
  });
  const [loading, setLoading] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
      if (isLogin) {
        setIsScanning(true);
        // Simulate biometric scan for 2 seconds
        await new Promise(resolve => setTimeout(resolve, 2000));
        setIsScanning(false);
        
        // Step 1: Authenticate and get JWT tokens
        const response = await authApi.login({
          username: formData.username,
          password: formData.password
        });
        
        const { access, refresh } = response.data;
        localStorage.setItem('altsan_token', access);
        localStorage.setItem('altsan_refresh', refresh);
        
        // Step 2: Fetch the real user profile from the server
        try {
          const profileResponse = await userApi.me();
          const serverRole = profileResponse.data.role || 'MEMBER';
          onLoginSuccess({
            username: profileResponse.data.username || formData.username,
            role: serverRole
          });
        } catch (profileErr) {
          // Fallback to form-selected role if /user/me/ fails
          console.warn("Could not fetch profile, using default:", profileErr);
          onLoginSuccess({
            username: formData.username,
            role: 'MEMBER'
          });
        }
      } else {
        // Registration Flow — call real backend API
        try {
          await authApi.register({
            username: formData.username,
            email: formData.email,
            password: formData.password,
            role: formData.role
          });
          
          setIsRegisterSuccess(true);
          
          // After showing success animation, auto-login
          setTimeout(async () => {
            try {
              const loginRes = await authApi.login({
                username: formData.username,
                password: formData.password
              });
              localStorage.setItem('altsan_token', loginRes.data.access);
              localStorage.setItem('altsan_refresh', loginRes.data.refresh);
              
              const profileRes = await userApi.me();
              setIsRegisterSuccess(false);
              onLoginSuccess({
                username: profileRes.data.username,
                role: profileRes.data.role
              });
            } catch (autoLoginErr) {
              setIsRegisterSuccess(false);
              setIsLogin(true); // Switch to login form
              setError('Account created! Please sign in.');
            }
          }, 2000);
        } catch (regErr) {
          const errMsg = regErr.response?.data?.error || 'Registration failed. Please try again.';
          setError(errMsg);
        }
      }
    } catch (err) {
      if (err.response?.status === 401) {
        setError("Invalid username or password.");
      } else if (err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError("Authentication Failed. Please check your credentials.");
      }
      console.error(err);
    } finally {
      setLoading(false);
      setIsScanning(false);
    }
  };

  return (
    <div className="auth-container">
      {/* Biometric Scanning Overlay */}
      <AnimatePresence>
        {isScanning && (
          <motion.div 
            className="registration-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
             <div className="biometric-scanner">
               <ScanFace size={64} className="text-blue" />
               <div className="scanner-laser"></div>
             </div>
             <motion.h2 
               initial={{ y: 10, opacity: 0 }} 
               animate={{ y: 0, opacity: 1 }} 
               transition={{ delay: 0.2 }}
             >
               Verifying Identity
             </motion.h2>
             <motion.p
               initial={{ y: 10, opacity: 0 }} 
               animate={{ y: 0, opacity: 1 }} 
               transition={{ delay: 0.3 }}
             >
               Please look at the screen...
             </motion.p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Registration Success Overlay */}
      <AnimatePresence>
        {isRegisterSuccess && (
          <motion.div 
            className="registration-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
             <div className="check-circle scale-in-anim">
               <CheckCircle2 size={40} strokeWidth={3} />
             </div>
             <motion.h2 
               initial={{ y: 10, opacity: 0 }} 
               animate={{ y: 0, opacity: 1 }} 
               transition={{ delay: 0.2 }}
             >
               Account Created!
             </motion.h2>
             <motion.p
               initial={{ y: 10, opacity: 0 }} 
               animate={{ y: 0, opacity: 1 }} 
               transition={{ delay: 0.3 }}
             >
               Logging you into your new dashboard...
             </motion.p>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="auth-glass-pane">
        <div className="auth-header">
          <div className="auth-logo">Altsan</div>
          <h1>{isLogin ? 'Welcome Back' : 'Create Account'}</h1>
          <p className="auth-subtitle">
            {isLogin 
              ? 'Enter your credentials to manage your society.' 
              : 'Register your details to access the facility network.'}
          </p>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>

          {error && (
            <div style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', padding: '12px 16px', borderRadius: '12px', fontSize: '14px', fontWeight: '600', marginBottom: '8px' }}>
              {error}
            </div>
          )}

          <div className="input-group">
            <label>Username</label>
            <input 
              type="text" 
              placeholder="e.g. sarah_murphy" 
              required
              value={formData.username}
              onChange={(e) => setFormData({...formData, username: e.target.value})}
            />
          </div>

          <AnimatePresence mode="wait">
            {!isLogin && (
              <motion.div 
                key="email-field"
                className="input-group"
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                style={{ overflow: 'hidden' }}
              >
                <label>Email Address</label>
                <input 
                  type="email" 
                  placeholder="sarah@example.com" 
                  required
                  value={formData.email}
                  onChange={(e) => setFormData({...formData, email: e.target.value})}
                />
              </motion.div>
            )}
          </AnimatePresence>

          <div className="input-group">
            <label>Password</label>
            <input 
              type="password" 
              placeholder="••••••••" 
              required
              value={formData.password}
              onChange={(e) => setFormData({...formData, password: e.target.value})}
            />
          </div>

          <AnimatePresence mode="wait">
            {!isLogin && (
              <motion.div 
                key="role-field"
                className="input-group"
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                style={{ overflow: 'hidden' }}
              >
                <label>Account Type</label>
                <select 
                  value={formData.role}
                  onChange={(e) => setFormData({...formData, role: e.target.value})}
                >
                  <option value="MEMBER">Resident / Facility Member</option>
                  <option value="CHAIRMAN">Chairman / Manager</option>
                  <option value="WORKER">Service Provider / Worker</option>
                  <option value="DIRECTOR">Executive Director</option>
                </select>
              </motion.div>
            )}
          </AnimatePresence>

          <button type="submit" className="btn-auth-submit" disabled={loading}>
            {loading ? (
               <div className="spinner"></div> 
            ) : (
               <>
                 {isLogin ? 'Sign In Securely' : 'Complete Registration'}
                 <ArrowRight size={18} style={{ marginLeft: '8px' }} />
               </>
            )}
          </button>
        </form>

        <div className="auth-footer">
          <p>
            {isLogin ? "Don't have an account?" : "Already have an account?"}
            <button type="button" className="btn-toggle" onClick={() => { setIsLogin(!isLogin); setError(''); }}>
              {isLogin ? 'Register Now' : 'Sign In'}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginRegistration;
