import React, { useState } from 'react';
import './Auth.css';

const LoginRegistration = ({ onLoginSuccess }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    role: 'CLIENT'
  });

  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    // Simulating API Call
    setTimeout(() => {
      setLoading(false);
      console.log("DEBUG: Auth Success", formData);
      onLoginSuccess(formData);
    }, 1500);
  };

  return (
    <div className="auth-container">
      <div className="auth-glass-pane">
        <div className="auth-header">
          <div className="auth-logo">AL</div>
          <h1>{isLogin ? 'Welcome Back' : 'Join Altus'}</h1>
          <p className="auth-subtitle">
            {isLogin 
              ? 'Enter your credentials to manage your facilities.' 
              : 'Create an account to start hiring verified professionals.'}
          </p>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          {!isLogin && (
            <div className="input-group">
              <label>Role</label>
              <select 
                value={formData.role} 
                onChange={(e) => setFormData({...formData, role: e.target.value})}
                className="role-selector"
              >
                <option value="CLIENT">Client (Hospital/Office)</option>
                <option value="WORKER">Worker (Service Provider)</option>
              </select>
            </div>
          )}

          <div className="input-group">
            <label>Username</label>
            <input 
              type="text" 
              placeholder="e.g. sarah_manager" 
              required
              value={formData.username}
              onChange={(e) => setFormData({...formData, username: e.target.value})}
            />
          </div>

          {!isLogin && (
            <div className="input-group">
              <label>Email Address</label>
              <input 
                type="email" 
                placeholder="sarah@hospital.com" 
                required
                value={formData.email}
                onChange={(e) => setFormData({...formData, email: e.target.value})}
              />
            </div>
          )}

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

          <button type="submit" className="btn-auth-submit" disabled={loading}>
            {loading ? <div className="spinner"></div> : (isLogin ? 'Sign In' : 'Create Account')}
          </button>
        </form>

        <div className="auth-footer">
          <p>
            {isLogin ? "Don't have an account?" : "Already have an account?"}
            <button className="btn-toggle" onClick={() => setIsLogin(!isLogin)}>
              {isLogin ? 'Register Now' : 'Sign In'}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginRegistration;
