import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  X, UploadCloud, MapPin, AlertTriangle, Send, Image as ImageIcon, CheckCircle2 
} from 'lucide-react';
import './ReportIssueModal.css';

const ReportIssueModal = ({ onClose, onSubmit }) => {
  const [formData, setFormData] = useState({
    category: 'maintenance',
    severity: 'low',
    location: '',
    description: ''
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  
  const fileInputRef = useRef(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setTimeout(() => {
      setIsSubmitting(false);
      setIsSuccess(true);
      setTimeout(() => {
        onSubmit(formData);
      }, 2000);
    }, 1500);
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const drawerVariants = {
    hidden: { y: "100%", opacity: 0 },
    visible: { y: 0, opacity: 1, transition: { type: "spring", damping: 25, stiffness: 200 } },
    exit: { y: "100%", opacity: 0, transition: { duration: 0.3 } }
  };

  return (
    <div className="report-drawer-overlay">
      <div className="report-drawer-backdrop" onClick={onClose} />
      
      <motion.div 
        className="report-drawer-container"
        variants={drawerVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
      >
        <div className="drawer-handle" />
        <button type="button" className="drawer-close-btn" onClick={onClose}>
          <X size={20} />
        </button>

        <AnimatePresence mode="wait">
          {!isSuccess ? (
            <motion.div 
              key="form"
              initial={{ opacity: 0 }} 
              animate={{ opacity: 1 }} 
              exit={{ opacity: 0 }}
              className="report-drawer-content"
            >
              <div className="report-header">
                <div className="report-icon-badge warning"><AlertTriangle size={24} /></div>
                <h2>Report an Issue</h2>
                <p>Send a direct ticket to the Altsan Operations Team.</p>
              </div>

              <form onSubmit={handleSubmit} className="report-form">
                
                {/* Sleek Pill selectors instead of dropdowns for 1-hand reachability */}
                <div className="form-group">
                  <label>Category</label>
                  <div className="touch-pill-grid">
                    {[
                      { id: 'maintenance', label: 'Maintenance' },
                      { id: 'cleaning', label: 'Cleaning' },
                      { id: 'security', label: 'Security' },
                      { id: 'other', label: 'Other' }
                    ].map(cat => (
                      <div 
                        key={cat.id} 
                        className={`touch-pill ${formData.category === cat.id ? 'active' : ''}`}
                        onClick={() => setFormData({...formData, category: cat.id})}
                      >
                        {cat.label}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="form-group">
                  <label>Priority Level</label>
                  <div className="touch-pill-grid priority-grid">
                    {[
                      { id: 'low', label: 'Low' },
                      { id: 'medium', label: 'Medium' },
                      { id: 'high', label: 'Urgent' }
                    ].map(sev => (
                      <div 
                        key={sev.id} 
                        className={`touch-pill ${formData.severity === sev.id ? 'active ' + sev.id : ''}`}
                        onClick={() => setFormData({...formData, severity: sev.id})}
                      >
                        {sev.label}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="form-group">
                  <label><MapPin size={14}/> Facility / Location</label>
                  <input 
                    type="text" 
                    name="location" 
                    className="sleek-input"
                    placeholder="e.g. Lobby B, Floor 3" 
                    value={formData.location}
                    onChange={handleChange}
                    required
                  />
                </div>

                <div className="form-group">
                  <label>Issue Description</label>
                  <textarea 
                    name="description" 
                    className="sleek-textarea"
                    placeholder="Provide details about the issue..."
                    rows="3"
                    value={formData.description}
                    onChange={handleChange}
                    required
                  />
                </div>

                <div className="form-group">
                  <label>Attach Photo (Optional)</label>
                  <div 
                    className={`drag-drop-zone ${dragActive ? 'drag-active' : ''} ${selectedFile ? 'has-file' : ''}`}
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <input 
                      ref={fileInputRef}
                      type="file" 
                      accept="image/*"
                      className="hidden-file-input"
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          setSelectedFile(e.target.files[0]);
                        }
                      }}
                    />
                    
                    {selectedFile ? (
                      <div className="file-selected-state">
                        <ImageIcon size={24} className="file-icon" />
                        <span className="file-name">{selectedFile.name}</span>
                        <button 
                          type="button"
                          className="btn-remove-file"
                          onClick={(e) => { e.stopPropagation(); setSelectedFile(null); }}
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ) : (
                      <div className="upload-prompt">
                        <UploadCloud size={32} className="upload-icon" />
                        <p>Tap to upload image</p>
                      </div>
                    )}
                  </div>
                </div>
              </form>
            </motion.div>
          ) : (
            <motion.div 
              key="success"
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="report-success-state"
            >
              <div className="success-icon-burst">
                <CheckCircle2 size={64} color="#10B981" />
              </div>
              <h2>Ticket Submitted</h2>
              <p>The Altsan Operations team has received your query and will dispatch a resolution unit shortly.</p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Action Button at the very bottom */}
        {!isSuccess && (
          <div className="report-drawer-footer">
            <button 
              type="button" 
              className={`report-btn-submit ${isSubmitting ? 'submitting' : ''}`}
              disabled={isSubmitting || !formData.location || !formData.description}
              onClick={handleSubmit}
            >
              {isSubmitting ? 'Submitting to Operations...' : (
                <>
                  <Send size={18} />
                  Submit Report
                </>
              )}
            </button>
          </div>
        )}
      </motion.div>
    </div>
  );
};

export default ReportIssueModal;
