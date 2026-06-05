import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  X, 
  UploadCloud, 
  MapPin, 
  AlertTriangle,
  Send,
  Image as ImageIcon,
  CheckCircle2
} from 'lucide-react';
import './ReportIssueModal.css';

const ReportIssueModal = ({ onClose, onSubmit }) => {
  const [formData, setFormData] = useState({
    title: '',
    category: 'maintenance',
    location: '',
    severity: 'low',
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
    // Simulate API call to supervisor console queue
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

  return (
    <div className="modal-overlay">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        className="report-modal"
      >
        <button type="button" className="wizard-close-btn" onClick={onClose} aria-label="Close">
          <X size={20} style={{ pointerEvents: 'none' }} />
        </button>

        <AnimatePresence mode="wait">
          {!isSuccess ? (
            <motion.div 
              key="form"
              initial={{ opacity: 0 }} 
              animate={{ opacity: 1 }} 
              exit={{ opacity: 0 }}
              className="report-content"
            >
              <div className="modal-header-alt">
                <div className="icon-badge warning"><AlertTriangle size={24} /></div>
                <h2>Report an Issue</h2>
                <p>Send a direct ticket to the Altsan Operations Team for resolution.</p>
              </div>

              <form onSubmit={handleSubmit} className="report-form">
                <div className="form-group-row">
                   <div className="form-group">
                    <label>Category</label>
                    <select name="category" value={formData.category} onChange={handleChange}>
                      <option value="maintenance">Maintenance & Repair</option>
                      <option value="cleaning">Cleaning / Hygiene</option>
                      <option value="security">Security Concern</option>
                      <option value="other">Other</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Priority</label>
                    <select name="severity" value={formData.severity} onChange={handleChange}>
                      <option value="low">Low - Routine</option>
                      <option value="medium">Medium - Needs Attention</option>
                      <option value="high">High - Urgent</option>
                    </select>
                  </div>
                </div>

                <div className="form-group glass-input">
                  <label><MapPin size={14}/> Facility / Location</label>
                  <input 
                    type="text" 
                    name="location" 
                    placeholder="e.g. Lobby B, Floor 3" 
                    value={formData.location}
                    onChange={handleChange}
                    required
                  />
                </div>

                <div className="form-group summary-input">
                  <label>Issue Description</label>
                  <textarea 
                    name="description" 
                    placeholder="Provide details about the issue..."
                    rows="3"
                    value={formData.description}
                    onChange={handleChange}
                    required
                  />
                </div>

                <div className="form-group file-upload-group">
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
                          className="btn-remove-file"
                          onClick={(e) => { e.stopPropagation(); setSelectedFile(null); }}
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ) : (
                      <div className="upload-prompt">
                        <UploadCloud size={32} className="upload-icon" />
                        <p>Click or drag image here</p>
                        <span className="upload-hint">SVG, PNG, JPG (max 5MB)</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="form-footer mt-4">
                  <button 
                    type="submit" 
                    className={`btn-primary-large full-width ${isSubmitting ? 'submitting' : ''}`}
                    disabled={isSubmitting || !formData.location || !formData.description}
                  >
                    {isSubmitting ? 'Submitting to Operations...' : (
                      <>
                        <Send size={18} />
                        Submit Report
                      </>
                    )}
                  </button>
                </div>
              </form>
            </motion.div>
          ) : (
            <motion.div 
              key="success"
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="success-state"
            >
              <div className="success-icon-large">
                <CheckCircle2 size={64} />
              </div>
              <h2>Ticket Submitted</h2>
              <p>The Altsan Operations team has received your query and will dispatch a resolution unit shortly.</p>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
};

export default ReportIssueModal;
