import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { workerApi } from '../utils/api';
import { ShieldAlert, FileSearch, CheckCircle2, XCircle, Clock, UserCheck, FileText, ChevronRight, X } from 'lucide-react';
import './WorkerVerification.css';

const WorkerVerification = () => {
  const [pendingWorkers, setPendingWorkers] = useState([]);
  const [selectedWorker, setSelectedWorker] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchPending = async () => {
    try {
      const res = await workerApi.pending();
      const mapped = res.data.map(w => ({
        id: `W-${w.id}`,
        dbId: w.id,
        name: w.user.username,
        skills: ["Facility Management"], // Could map from backend tags if added
        submittedAt: new Date(w.created_at || Date.now()).toLocaleDateString(),
        documents: ["ID_Proof.pdf"],
        riskScore: "Low"
      }));
      setPendingWorkers(mapped);
    } catch (err) {
      console.error("Failed to fetch pending workers", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPending();
  }, []);

  const handleVerify = async (workerId, action) => {
    try {
      await workerApi.verify(workerId, action);
      setSelectedWorker(null);
      fetchPending(); // Refresh list
    } catch (err) {
      console.error(`Failed to ${action} worker`, err);
      alert(`Could not ${action} worker. Please try again.`);
    }
  };

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.1 } }
  };

  const itemVariants = {
    hidden: { y: 20, opacity: 0 },
    visible: { y: 0, opacity: 1 }
  };

  const drawerVariants = {
    hidden: { y: "100%", opacity: 0 },
    visible: { y: 0, opacity: 1, transition: { type: "spring", damping: 25, stiffness: 200 } },
    exit: { y: "100%", opacity: 0, transition: { duration: 0.3 } }
  };

  return (
    <div className="security-portal-light">
      <header className="spl-header">
        <div className="spl-brand">
          <ShieldAlert size={28} className="spl-icon" />
          <div>
            <h1>Identity Verification</h1>
            <p>Access Control & Clearance</p>
          </div>
        </div>
      </header>

      {/* Main List (1-Hand Friendly) */}
      <main className="spl-main">
        <div className="spl-stats-row">
          <div className="spl-stat">
            <span>Pending</span>
            <strong>{pendingWorkers.length}</strong>
          </div>
          <div className="spl-stat urgent">
            <span>Urgent</span>
            <strong>1</strong>
          </div>
        </div>

        <motion.div className="spl-queue" variants={containerVariants} initial="hidden" animate="visible">
          {pendingWorkers.map(worker => (
            <motion.div 
              key={worker.id} 
              variants={itemVariants}
              whileTap={{ scale: 0.98 }}
              className="spl-card"
              onClick={() => setSelectedWorker(worker)}
            >
              <div className="spl-card-left">
                <div className="spl-avatar">
                  {worker.name.charAt(0)}
                  <div className={`spl-risk-dot ${worker.riskScore.toLowerCase()}`} />
                </div>
                <div className="spl-info">
                  <strong>{worker.name}</strong>
                  <span><Clock size={12} /> {worker.submittedAt}</span>
                </div>
              </div>
              <ChevronRight size={20} className="spl-chevron" />
            </motion.div>
          ))}
        </motion.div>
      </main>

      {/* 1-Handed Bottom Drawer for details */}
      <AnimatePresence>
        {selectedWorker && (
          <div className="spl-drawer-overlay">
            <div className="spl-drawer-backdrop" onClick={() => setSelectedWorker(null)} />
            <motion.div 
              className="spl-drawer"
              variants={drawerVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
            >
              <div className="spl-drawer-handle" />
              <button className="spl-drawer-close" onClick={() => setSelectedWorker(null)}>
                <X size={20} />
              </button>

              <div className="spl-drawer-content">
                <div className="spl-dossier-header">
                  <h2>{selectedWorker.name}</h2>
                  <span className="spl-badge-id">{selectedWorker.id}</span>
                </div>

                <div className="spl-section">
                  <h3><UserCheck size={16} /> Declared Skills</h3>
                  <div className="spl-tags">
                    {selectedWorker.skills.map(skill => (
                      <span key={skill} className="spl-tag">{skill}</span>
                    ))}
                  </div>
                </div>

                <div className="spl-section">
                  <h3>System Risk Assessment</h3>
                  <div className={`spl-risk-panel ${selectedWorker.riskScore.toLowerCase()}`}>
                    <strong>{selectedWorker.riskScore} Risk</strong>
                    <p>Automated checks completed. Manual review required.</p>
                  </div>
                </div>

                <div className="spl-section">
                  <h3><FileSearch size={16} /> Document Vault</h3>
                  <div className="spl-vault-list">
                    {selectedWorker.documents.map(doc => (
                      <div key={doc} className="spl-vault-file">
                        <FileText size={20} className="vf-icon" />
                        <div className="vf-info">
                          <strong>{doc}</strong>
                          <span>PDF • Encrypted</span>
                        </div>
                        <button className="vf-view">View</button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Action Buttons at the very bottom (thumb reach) */}
              <div className="spl-drawer-footer">
                <button className="spl-btn-reject" onClick={() => handleVerify(selectedWorker.dbId, 'reject')}>
                  Reject
                </button>
                <button className="spl-btn-approve" onClick={() => handleVerify(selectedWorker.dbId, 'approve')}>
                  <CheckCircle2 size={18} /> Approve
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default WorkerVerification;
