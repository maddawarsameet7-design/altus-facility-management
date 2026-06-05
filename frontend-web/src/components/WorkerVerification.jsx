import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ShieldAlert, FileSearch, CheckCircle2, XCircle, Clock, UserCheck, FileText, ChevronRight } from 'lucide-react';
import './WorkerVerification.css';

const WorkerVerification = () => {
  const [pendingWorkers, setPendingWorkers] = useState([
    {
      id: "W-502",
      name: "John Miller",
      skills: ["Housekeeping", "Maintenance"],
      submittedAt: "2 hours ago",
      documents: ["ID_Proof.pdf", "Background_Check.pdf", "Experience_Letter.pdf"],
      riskScore: "Low"
    },
    {
      id: "W-505",
      name: "Arjun Sharma",
      skills: ["Electrician", "Plumbing"],
      submittedAt: "5 hours ago",
      documents: ["ID_Proof.jpg", "Certification.pdf"],
      riskScore: "Medium"
    }
  ]);

  const [selectedWorker, setSelectedWorker] = useState(null);

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.1 } }
  };

  const itemVariants = {
    hidden: { x: -20, opacity: 0 },
    visible: { x: 0, opacity: 1 }
  };

  return (
    <div className="security-portal">
      <header className="security-header">
        <div className="sh-brand">
          <ShieldAlert size={28} className="sh-icon" />
          <div>
            <h1>Identity Verification</h1>
            <p>Access Control & Background Clearance</p>
          </div>
        </div>
        <div className="sh-stats">
          <div className="sh-stat-box">
            <span>Pending Clearance</span>
            <strong>{pendingWorkers.length}</strong>
          </div>
          <div className="sh-stat-box danger">
            <span>Urgent Review</span>
            <strong>1</strong>
          </div>
        </div>
      </header>

      <div className="security-grid">
        {/* Sidebar */}
        <aside className="security-sidebar">
          <h3>Verification Queue</h3>
          <motion.div className="queue-list" variants={containerVariants} initial="hidden" animate="visible">
            {pendingWorkers.map(worker => (
              <motion.div 
                key={worker.id} 
                variants={itemVariants}
                className={`queue-card ${selectedWorker?.id === worker.id ? 'active' : ''}`}
                onClick={() => setSelectedWorker(worker)}
              >
                <div className="qc-avatar">
                  {worker.name.charAt(0)}
                  <div className={`risk-dot ${worker.riskScore.toLowerCase()}`} />
                </div>
                <div className="qc-info">
                  <strong>{worker.name}</strong>
                  <span><Clock size={12} /> {worker.submittedAt}</span>
                </div>
                <div className="qc-id">{worker.id}</div>
              </motion.div>
            ))}
          </motion.div>
        </aside>

        {/* Detail Panel */}
        <main className="security-main">
          <AnimatePresence mode="wait">
            {selectedWorker ? (
              <motion.div 
                key={selectedWorker.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="clearance-dossier"
              >
                <div className="dossier-header">
                  <div className="dh-left">
                    <h2>{selectedWorker.name}</h2>
                    <span className="dh-id badge-id">{selectedWorker.id}</span>
                  </div>
                  <div className="dh-actions">
                    <button className="btn-reject"><XCircle size={18} /> Reject</button>
                    <button className="btn-approve"><CheckCircle2 size={18} /> Grant Clearance</button>
                  </div>
                </div>

                <div className="dossier-grid">
                  <section className="d-section skills-section">
                    <h3><UserCheck size={16} /> Declared Skills</h3>
                    <div className="hacker-tags">
                      {selectedWorker.skills.map(skill => (
                        <span key={skill} className="h-tag">{skill}</span>
                      ))}
                    </div>
                  </section>
                  
                  <section className="d-section risk-section">
                    <h3>System Risk Assessment</h3>
                    <div className={`risk-panel ${selectedWorker.riskScore.toLowerCase()}`}>
                      <strong>{selectedWorker.riskScore} Risk</strong>
                      <p>Automated checks completed. Manual document review required.</p>
                    </div>
                  </section>
                </div>

                <section className="d-section docs-section">
                  <h3><FileSearch size={16} /> Document Vault</h3>
                  <div className="doc-vault-grid">
                    {selectedWorker.documents.map(doc => (
                      <div key={doc} className="vault-file">
                        <div className="vf-icon"><FileText size={24} /></div>
                        <div className="vf-info">
                          <strong>{doc}</strong>
                          <span>Secure PDF • Encrypted</span>
                        </div>
                        <button className="vf-view"><ChevronRight size={20} /></button>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="d-section logs-section">
                  <h3>Internal Clearance Logs</h3>
                  <textarea placeholder="Append notes to clearance file..."></textarea>
                </section>
              </motion.div>
            ) : (
              <div className="security-empty-state">
                <div className="ses-icon-container pulse-ring">
                  <ShieldAlert size={64} className="ses-icon" />
                </div>
                <h3>Awaiting Selection</h3>
                <p>Select a candidate from the queue to review their clearance dossier.</p>
              </div>
            )}
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
};

export default WorkerVerification;
