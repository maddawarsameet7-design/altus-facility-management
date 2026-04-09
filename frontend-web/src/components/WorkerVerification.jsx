import React, { useState } from 'react';
import './WorkerVerification.css';

const WorkerVerification = () => {
  const [pendingWorkers, setPendingWorkers] = useState([
    {
      id: "W-502",
      name: "John Miller",
      skills: ["Housekeeping", "Maintenance"],
      submittedAt: "2 hours ago",
      documents: ["ID_Proof.pdf", "Background_Check.pdf", "Experience_Letter.pdf"]
    },
    {
      id: "W-505",
      name: "Arjun Sharma",
      skills: ["Electrician", "Plumbing"],
      submittedAt: "5 hours ago",
      documents: ["ID_Proof.jpg", "Certification.pdf"]
    }
  ]);

  const [selectedWorker, setSelectedWorker] = useState(null);

  return (
    <div className="admin-container">
      <header className="admin-header">
        <div className="title-group">
          <h1>Worker Verifications</h1>
          <p>Review and onboard new service providers to the platform.</p>
        </div>
        <div className="stats-mini">
          <div className="stat">
            <span className="label">Total Pending</span>
            <span className="value">12</span>
          </div>
          <div className="stat highlight">
            <span className="label">Urgent</span>
            <span className="value">3</span>
          </div>
        </div>
      </header>

      <div className="verification-layout">
        {/* Sidebar List */}
        <aside className="verification-list">
          <h3>Pending Requests</h3>
          <div className="list-items">
            {pendingWorkers.map(worker => (
              <div 
                key={worker.id} 
                className={`worker-item ${selectedWorker?.id === worker.id ? 'active' : ''}`}
                onClick={() => setSelectedWorker(worker)}
              >
                <div className="worker-avatar">{worker.name.charAt(0)}</div>
                <div className="worker-info">
                  <strong>{worker.name}</strong>
                  <span>{worker.submittedAt}</span>
                </div>
                <div className="badge">{worker.id}</div>
              </div>
            ))}
          </div>
        </aside>

        {/* Detail Panel */}
        <main className="verification-detail">
          {selectedWorker ? (
            <div className="detail-card animate-fade-in">
              <div className="detail-header">
                <h2>{selectedWorker.name}</h2>
                <div className="actions">
                  <button className="btn-reject">Reject Profile</button>
                  <button className="btn-approve">Approve & Notify</button>
                </div>
              </div>

              <section className="detail-section">
                <h3>Skills & Categories</h3>
                <div className="tag-cloud">
                  {selectedWorker.skills.map(skill => (
                    <span key={skill} className="skill-tag">{skill}</span>
                  ))}
                </div>
              </section>

              <section className="detail-section">
                <h3>Documents Ready for Review</h3>
                <div className="document-grid">
                  {selectedWorker.documents.map(doc => (
                    <div key={doc} className="doc-item">
                      <div className="doc-icon">📄</div>
                      <div className="doc-info">
                        <strong>{doc}</strong>
                        <span>PDF Document • 2.4 MB</span>
                      </div>
                      <button className="btn-view">View</button>
                    </div>
                  ))}
                </div>
              </section>

              <section className="detail-section comment-section">
                <h3>Internal Notes</h3>
                <textarea placeholder="Add a note for other admins..."></textarea>
              </section>
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-icon">📂</div>
              <h3>Select a worker request to begin verification</h3>
              <p>Verify identity documents and skills before granting access.</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default WorkerVerification;
