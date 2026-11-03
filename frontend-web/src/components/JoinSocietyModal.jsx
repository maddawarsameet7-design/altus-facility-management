import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Building2, Key, CheckCircle2, AlertCircle, X, Loader2 } from 'lucide-react';
import { societyApi } from '../utils/api';
import useStore from '../store/useStore';
import './JoinSocietyModal.css';

const JoinSocietyModal = ({ isOpen, onClose }) => {
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [successData, setSuccessData] = useState(null);
  const { fetchUserSocieties } = useStore();

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    const cleanCode = code.trim().toUpperCase();
    if (!cleanCode) {
      setError('Please enter an invite code.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const res = await societyApi.join(cleanCode);
      setSuccessData(res.data);
      if (fetchUserSocieties) {
        await fetchUserSocieties();
      }
    } catch (err) {
      const msg = err.response?.data?.error || err.message || 'Failed to join society. Please check your code.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setCode('');
    setError('');
    setSuccessData(null);
    onClose();
  };

  return (
    <div className="join-modal-backdrop" onClick={handleClose}>
      <motion.div
        className="join-modal-card glass-card"
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, scale: 0.9, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.9, y: 20 }}
      >
        <button className="join-modal-close" onClick={handleClose} aria-label="Close">
          <X size={20} />
        </button>

        {!successData ? (
          <div>
            <div className="join-modal-header">
              <div className="join-icon-box">
                <Building2 size={28} className="text-blue" />
              </div>
              <h2>Join Client Society</h2>
              <p>Enter the invite code provided by your Society Chairman or Altus Administrator.</p>
            </div>

            {error && (
              <motion.div
                className="join-error-banner"
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <AlertCircle size={16} />
                <span>{error}</span>
              </motion.div>
            )}

            <form onSubmit={handleSubmit} className="join-form">
              <div className="join-input-group">
                <Key size={18} className="join-input-icon" />
                <input
                  type="text"
                  placeholder="e.g. ALTUS-A1B2C3D4E5"
                  value={code}
                  onChange={(e) => setCode(e.target.value.toUpperCase())}
                  autoFocus
                  disabled={loading}
                />
              </div>

              <div className="join-actions">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={handleClose}
                  disabled={loading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={loading || !code.trim()}
                >
                  {loading ? (
                    <>
                      <Loader2 size={16} className="spinner" />
                      <span>Verifying...</span>
                    </>
                  ) : (
                    <span>Submit Code</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        ) : (
          <div className="join-success-view">
            <div className="join-success-icon">
              <CheckCircle2 size={48} color="#10B981" />
            </div>
            <h3>Request Submitted!</h3>
            <p className="join-success-msg">
              {successData.message || `You have requested to join ${successData.society}.`}
            </p>
            <div className="join-status-pill">
              Status: <strong>{successData.status?.toUpperCase() || 'PENDING APPROVAL'}</strong>
            </div>
            <button className="btn-primary full-width" onClick={handleClose}>
              Done
            </button>
          </div>
        )}
      </motion.div>
    </div>
  );
};

export default JoinSocietyModal;

