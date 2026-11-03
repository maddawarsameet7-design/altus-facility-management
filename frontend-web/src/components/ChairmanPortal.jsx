import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Building2, Users, UserCheck, UserX, Key, Copy, Check, 
  Clock, Shield, RefreshCw, AlertCircle, Plus, Sparkles 
} from 'lucide-react';
import { societyApi } from '../utils/api';
import useStore from '../store/useStore';
import './ChairmanPortal.css';

const ChairmanPortal = () => {
  const { currentSociety } = useStore();
  const [activeTab, setActiveTab] = useState('pending'); // 'pending' | 'members' | 'invite'
  const [pendingMembers, setPendingMembers] = useState([]);
  const [activeMembers, setActiveMembers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(null);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // Invite generation state
  const [maxUses, setMaxUses] = useState(5);
  const [expiresInDays, setExpiresInDays] = useState(7);
  const [generatedInvite, setGeneratedInvite] = useState(null);
  const [copied, setCopied] = useState(false);

  const societyId = currentSociety?.id;

  const loadMembers = useCallback(async () => {
    if (!societyId) return;
    setLoading(true);
    setError('');
    try {
      const [pendingRes, allRes] = await Promise.all([
        societyApi.getMembers(societyId, true),
        societyApi.getMembers(societyId, false)
      ]);
      setPendingMembers(Array.isArray(pendingRes.data) ? pendingRes.data : (pendingRes.data?.results || []));
      const all = Array.isArray(allRes.data) ? allRes.data : (allRes.data?.results || []);
      setActiveMembers(all.filter(m => m.is_active));
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to load society members.');
    } finally {
      setLoading(false);
    }
  }, [societyId]);

  useEffect(() => {
    loadMembers();
  }, [loadMembers]);

  const handleApprove = async (userId) => {
    setActionLoading(userId);
    setError('');
    try {
      await societyApi.approveMember(societyId, userId);
      setSuccessMsg('Member approved successfully! ✅');
      setTimeout(() => setSuccessMsg(''), 3000);
      await loadMembers();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to approve member.');
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (userId) => {
    if (!window.confirm('Are you sure you want to reject and remove this membership request?')) {
      return;
    }
    setActionLoading(userId);
    setError('');
    try {
      await societyApi.rejectMember(societyId, userId);
      setSuccessMsg('Membership request rejected.');
      setTimeout(() => setSuccessMsg(''), 3000);
      await loadMembers();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to reject member.');
    } finally {
      setActionLoading(null);
    }
  };

  const handleCreateInvite = async (e) => {
    e.preventDefault();
    if (!societyId) return;
    setLoading(true);
    setError('');
    try {
      const expiryDate = new Date();
      expiryDate.setDate(expiryDate.getDate() + parseInt(expiresInDays, 10));

      const res = await societyApi.createInvite(societyId, {
        role: 'MEMBER',
        max_uses: parseInt(maxUses, 10),
        expires_at: expiryDate.toISOString()
      });
      setGeneratedInvite(res.data);
      setSuccessMsg('New invite code created!');
      setTimeout(() => setSuccessMsg(''), 4000);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to create invite code.');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!societyId) {
    return (
      <div className="chairman-empty-state">
        <Building2 size={48} className="text-muted" />
        <h3>No Society Selected</h3>
        <p>Please select your society from the top header to manage members.</p>
      </div>
    );
  }

  return (
    <div className="chairman-portal-container">
      {/* Header Banner */}
      <header className="chairman-header shadow-glass">
        <div className="chairman-header-left">
          <div className="chairman-icon-box">
            <Shield size={28} color="#3b82f6" />
          </div>
          <div>
            <h1>{currentSociety.name || 'Society Portal'}</h1>
            <p className="chairman-subtitle">
              Chairman Administration Console • {activeMembers.length} Active Members
            </p>
          </div>
        </div>

        <button className="chairman-refresh-btn" onClick={loadMembers} disabled={loading} title="Refresh">
          <RefreshCw size={18} className={loading ? 'spinner' : ''} />
        </button>
      </header>

      {/* Notifications */}
      {successMsg && (
        <motion.div className="chairman-alert success" initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}>
          <span>{successMsg}</span>
        </motion.div>
      )}
      {error && (
        <motion.div className="chairman-alert error" initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}>
          <AlertCircle size={16} />
          <span>{error}</span>
        </motion.div>
      )}

      {/* Navigation Tabs */}
      <div className="chairman-tabs">
        <button 
          className={`chairman-tab ${activeTab === 'pending' ? 'active' : ''}`}
          onClick={() => setActiveTab('pending')}
        >
          <UserCheck size={18} />
          <span>Pending Approvals</span>
          {pendingMembers.length > 0 && (
            <span className="tab-badge">{pendingMembers.length}</span>
          )}
        </button>

        <button 
          className={`chairman-tab ${activeTab === 'members' ? 'active' : ''}`}
          onClick={() => setActiveTab('members')}
        >
          <Users size={18} />
          <span>Active Directory</span>
          <span className="tab-count">({activeMembers.length})</span>
        </button>

        <button 
          className={`chairman-tab ${activeTab === 'invite' ? 'active' : ''}`}
          onClick={() => setActiveTab('invite')}
        >
          <Key size={18} />
          <span>Generate Invite Code</span>
        </button>
      </div>

      {/* Tab 1: Pending Approvals */}
      {activeTab === 'pending' && (
        <div className="tab-content">
          {pendingMembers.length === 0 ? (
            <div className="empty-pending-card white-card">
              <UserCheck size={40} color="#10b981" />
              <h3>All Caught Up!</h3>
              <p>There are no pending membership requests waiting for your approval.</p>
            </div>
          ) : (
            <div className="members-grid">
              {pendingMembers.map((m) => (
                <motion.div 
                  key={m.id} 
                  className="member-card white-card"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                >
                  <div className="member-card-header">
                    <div className="member-avatar">
                      {(m.user?.username || 'U')[0].toUpperCase()}
                    </div>
                    <div>
                      <h4>{m.user?.username}</h4>
                      <p className="member-email">{m.user?.email || 'No email provided'}</p>
                    </div>
                  </div>

                  <div className="member-details">
                    <div className="detail-item">
                      <span className="detail-label">Flat / Unit</span>
                      <strong className="detail-val">{m.flat_or_unit || 'General Member'}</strong>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Role</span>
                      <strong className="detail-val">{m.role}</strong>
                    </div>
                  </div>

                  <div className="member-card-actions">
                    <button
                      className="btn-reject"
                      onClick={() => handleReject(m.user?.id)}
                      disabled={actionLoading === m.user?.id}
                    >
                      <UserX size={16} />
                      <span>Reject</span>
                    </button>
                    <button
                      className="btn-approve"
                      onClick={() => handleApprove(m.user?.id)}
                      disabled={actionLoading === m.user?.id}
                    >
                      <UserCheck size={16} />
                      <span>{actionLoading === m.user?.id ? 'Approving...' : 'Approve'}</span>
                    </button>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Active Members Directory */}
      {activeTab === 'members' && (
        <div className="tab-content">
          <div className="directory-list white-card">
            <div className="directory-header">
              <h3>Resident Members</h3>
              <span className="directory-total">{activeMembers.length} Verified</span>
            </div>

            <div className="directory-rows">
              {activeMembers.map((m) => (
                <div key={m.id} className="directory-row">
                  <div className="directory-left">
                    <div className="directory-avatar">
                      {(m.user?.username || 'U')[0].toUpperCase()}
                    </div>
                    <div>
                      <strong>{m.user?.username}</strong>
                      <span className="directory-sub">
                        {m.flat_or_unit ? `Unit: ${m.flat_or_unit}` : 'Resident'}
                      </span>
                    </div>
                  </div>

                  <div className="directory-right">
                    <span className={`role-tag role-${m.role.toLowerCase()}`}>
                      {m.role}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Invite Generator */}
      {activeTab === 'invite' && (
        <div className="tab-content">
          <div className="invite-generator-card white-card">
            <div className="invite-card-head">
              <div className="key-icon-wrapper">
                <Key size={24} color="#2563eb" />
              </div>
              <div>
                <h3>Create Resident Invite Code</h3>
                <p>Share this code with new residents so they can join {currentSociety.name}.</p>
              </div>
            </div>

            <form onSubmit={handleCreateInvite} className="invite-form">
              <div className="form-row">
                <div className="form-group">
                  <label>Max Allowed Uses</label>
                  <select value={maxUses} onChange={(e) => setMaxUses(e.target.value)}>
                    <option value="1">1 time (Single Use)</option>
                    <option value="5">5 residents</option>
                    <option value="20">20 residents</option>
                    <option value="100">100 residents</option>
                  </select>
                </div>

                <div className="form-group">
                  <label>Expires In</label>
                  <select value={expiresInDays} onChange={(e) => setExpiresInDays(e.target.value)}>
                    <option value="1">24 Hours</option>
                    <option value="7">7 Days</option>
                    <option value="30">30 Days</option>
                    <option value="90">90 Days</option>
                  </select>
                </div>
              </div>

              <button type="submit" className="btn-generate" disabled={loading}>
                <Sparkles size={18} />
                <span>{loading ? 'Generating...' : 'Generate New Code'}</span>
              </button>
            </form>

            {generatedInvite && (
              <motion.div 
                className="generated-code-box"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
              >
                <div className="code-box-header">
                  <span>Active Invite Code</span>
                  <span className="code-uses">Max {generatedInvite.max_uses} Uses</span>
                </div>

                <div className="code-display-row">
                  <code className="invite-code-text">{generatedInvite.code}</code>
                  <button 
                    className={`btn-copy ${copied ? 'copied' : ''}`}
                    onClick={() => copyToClipboard(generatedInvite.code)}
                  >
                    {copied ? <Check size={18} /> : <Copy size={18} />}
                    <span>{copied ? 'Copied!' : 'Copy'}</span>
                  </button>
                </div>

                <p className="code-instruction">
                  Residents can tap <strong>"Join Society"</strong> in their Altsan app and paste this code.
                </p>
              </motion.div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default ChairmanPortal;

