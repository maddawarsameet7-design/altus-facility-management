import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { categoryApi } from '../utils/api';
import { 
  Sparkles, 
  Shield, 
  Zap, 
  Droplets, 
  ChevronRight, 
  ChevronLeft, 
  X,
  Calendar,
  Clock,
  Building2,
  Users,
  Award,
  Star,
  Leaf,
  Trash2,
  Film,
  Music,
  Activity,
  FileText
} from 'lucide-react';
import './BookingWizard.css';

const vendors = [
  { id: 'v-1', name: 'Elite Cleaners Corp', specialization: 'Hospital Grade Sanitization', rating: 4.9, price: '₹28/hr', icon: Award },
  { id: 'v-2', name: 'Society Shine Partners', specialization: 'Residential & Common Areas', rating: 4.7, price: '₹22/hr', icon: Building2 },
  { id: 'v-3', name: 'Rapid Response Hygiene', specialization: 'Emergency & Bio-Hazard', rating: 4.8, price: '₹35/hr', icon: Zap }
];

const getStyleForCategory = (name) => {
  const map = {
    'Housekeeping': { icon: Sparkles, color: '#10B981', roles: ['chairman'] },
    'Security Guard': { icon: Shield, color: '#6366F1', roles: ['chairman'] },
    'Gardening': { icon: Leaf, color: '#84CC16', roles: ['chairman'] },
    'Waste Management': { icon: Trash2, color: '#6B7280', roles: ['chairman', 'member'] },
    'Electrician': { icon: Zap, color: '#F59E0B', roles: ['member'] },
    'Plumber': { icon: Droplets, color: '#0EA5E9', roles: ['member'] }
  };
  return map[name] || { icon: FileText, color: '#666', roles: ['member'] };
};

const BookingWizard = ({ onClose, onSuccess, currentRole }) => {
  const [step, setStep] = useState(1);
  const [services, setServices] = useState([]);
  const [selectedService, setSelectedService] = useState(null);
  const [selectedVendor, setSelectedVendor] = useState(null);
  const [workerCount, setWorkerCount] = useState(1);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadCategories = async () => {
      try {
        const response = await categoryApi.getAll();
        const enriched = response.data.map(cat => ({
          ...cat,
          category: cat.name,
          ...getStyleForCategory(cat.name),
          basePrice: `₹${cat.base_hourly_rate}/hr`
        }));
        setServices(enriched);
      } catch (err) {
        console.error("Failed to load categories");
      } finally {
        setLoading(false);
      }
    };
    loadCategories();
  }, []);
  
  const currentService = services.find(s => s.id === selectedService);
  const isMarketplaceFlow = currentService?.category === 'Housekeeping';
  const totalSteps = isMarketplaceFlow ? 4 : 3;
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const handleConfirmOrder = () => {
    setIsSubmitting(true);
    // Real API integration handled in App.jsx onSuccess
    setTimeout(() => {
      setIsSubmitting(false);
      setIsSuccess(true);
      setTimeout(() => {
        onSuccess(currentService);
      }, 1500);
    }, 1000);
  };

  const containerVariants = {
    hidden: { opacity: 0, scale: 0.95 },
    visible: { opacity: 1, scale: 1, transition: { duration: 0.3, ease: "easeOut" } },
    exit: { opacity: 0, scale: 0.95, transition: { duration: 0.2, ease: "easeIn" } }
  };

  const stepVariants = {
    initial: { x: 20, opacity: 0 },
    enter: { x: 0, opacity: 1, transition: { duration: 0.4, ease: "easeOut" } },
    exit: { x: -20, opacity: 0, transition: { duration: 0.3, ease: "easeIn" } }
  };

  return (
    <div className="modal-overlay">
      <motion.div 
        className="wizard-container"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
      >
        <button type="button" className="wizard-close-btn" onClick={onClose} aria-label="Close Wizard">
          <X size={20} style={{ pointerEvents: 'none' }} />
        </button>
        
          <div className="wizard-header">
            <h2>Book a Service</h2>
            <div className="progress-container">
              <div className="progress-bar-wrapper">
                <div className="progress-bar-track">
                    <motion.div 
                      className="progress-bar-fill" 
                      initial={{ width: `${(1 / totalSteps) * 100}%` }}
                      animate={{ width: `${(isSuccess ? totalSteps : step) / totalSteps * 100}%` }}
                      style={{ backgroundColor: isSuccess ? '#10B981' : 'var(--primary)' }}
                    />
                  </div>
                </div>
                <div className="progress-steps-labels">
                  <span className={step >= 1 ? 'active' : ''}>Service</span>
                  {isMarketplaceFlow && <span className={step >= 2 ? 'active' : ''}>Partner</span>}
                  <span className={step >= (isMarketplaceFlow ? 3 : 2) ? 'active' : ''}>Schedule</span>
                  <span className={step >= totalSteps || isSuccess ? 'active' : ''}>Review</span>
                </div>
            </div>
          </div>

        <div className="wizard-body">
          <AnimatePresence mode="wait">
            {step === 1 && (
              <motion.div 
                key="step1"
                variants={stepVariants}
                initial="initial"
                animate="enter"
                exit="exit"
                className="step-content"
              >
                <div className="step-header">
                  <h3>Select a Service Category</h3>
                  <p className="subtitle">Choose the type of professional required for the facility.</p>
                </div>
                
                <div className="services-grid">
                  {services.filter(s => currentRole === 'chairman' ? s.roles.includes('chairman') : s.roles.includes('member')).map(service => {
                    const Icon = service.icon;
                    return (
                      <motion.div 
                        key={service.id}
                        whileHover={{ y: -5 }}
                        whileTap={{ scale: 0.98 }}
                        className={`service-card ${selectedService === service.id ? 'selected' : ''}`}
                        onClick={() => setSelectedService(service.id)}
                      >
                        <div className="service-icon-box" style={{ backgroundColor: `${service.color}15`, color: service.color }}>
                          <Icon size={28} />
                        </div>
                        <div className="service-info">
                          <h4>{service.category}</h4>
                          <p>{service.description}</p>
                        </div>
                        <div className="service-price-tag">
                          <span>from</span>
                          <strong>{service.basePrice}</strong>
                        </div>
                        {selectedService === service.id && (
                          <div className="selection-badge">
                            <Shield size={12} fill="currentColor" />
                          </div>
                        )}
                      </motion.div>
                    );
                  })}
                </div>
              </motion.div>
            )}

            {step === 2 && isMarketplaceFlow && (
              <motion.div 
                key="step-vendor"
                variants={stepVariants}
                initial="initial"
                animate="enter"
                exit="exit"
                className="step-content"
              >
                <div className="step-header">
                  <h3>Select a Service Partner</h3>
                  <p className="subtitle">Choose a curated vendor for your facility's housekeeping needs.</p>
                </div>
                
                <div className="vendors-list-layout">
                  {vendors.map(vendor => (
                    <motion.div 
                      key={vendor.id}
                      whileHover={{ scale: 1.01 }}
                      className={`vendor-select-card ${selectedVendor === vendor.id ? 'active' : ''}`}
                      onClick={() => setSelectedVendor(vendor.id)}
                    >
                      <div className="vendor-card-header">
                        <div className="v-icon-box">
                          {(() => {
                            const Icon = vendor.icon;
                            return <Icon size={20} />;
                          })()}
                        </div>
                        <div className="v-core-info">
                          <h4>{vendor.name}</h4>
                          <span className="v-spec">{vendor.specialization}</span>
                        </div>
                        <div className="v-rating"><Star size={14} fill="currentColor" stroke="none" /> {vendor.rating}</div>
                      </div>
                      <div className="vendor-card-footer">
                        <span className="v-rate-label">Standard Rate:</span>
                        <span className="v-price">{vendor.price}</span>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </motion.div>
            )}

            {step === (isMarketplaceFlow ? 3 : 2) && (
              <motion.div 
                key="step-schedule"
                variants={stepVariants}
                initial="initial"
                animate="enter"
                exit="exit"
                className="step-content"
              >
                <div className="step-header">
                  <h3>Schedule & Details</h3>
                  <p className="subtitle">Set the timeframe and specific facility location.</p>
                </div>
                
                <div className="form-layout">
                  {selectedService?.id === 'srv-4' ? (
                    <div style={{ background: 'rgba(16, 185, 129, 0.1)', color: '#10B981', padding: '16px', borderRadius: '12px', marginBottom: '20px', fontSize: '14px', fontWeight: 'bold' }}>
                      Waste collection is a complimentary service scheduled automatically everyday at 09:00 AM.
                    </div>
                  ) : (
                    <div className="form-row">
                      <div className="form-field glass-input">
                        <label><Calendar size={14} /> Date</label>
                        <input type="date" />
                      </div>
                      <div className="form-field glass-input">
                        <label><Clock size={14} /> Start Time</label>
                        <input type="time" />
                      </div>
                    </div>
                  )}

                  <div className="form-field glass-input">
                    <label><Building2 size={14} /> Select Property Facility</label>
                    <select>
                      <option>Block A Common Area</option>
                      <option>Block B Corridors</option>
                      <option>Main Entrance Gate</option>
                      <option>Resident Flat</option>
                    </select>
                  </div>

                  <div className="form-field glass-input">
                    <label><Users size={14} /> Number of Workers Needed</label>
                    <div className="counter-horizontal">
                      <button onClick={() => setWorkerCount(Math.max(1, workerCount - 1))} className="counter-btn">-</button>
                      <div className="counter-display">{workerCount}</div>
                      <button onClick={() => setWorkerCount(workerCount + 1)} className="counter-btn">+</button>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {step === totalSteps && !isSuccess && !isSubmitting && (
              <motion.div 
                key="step-review"
                variants={stepVariants}
                initial="initial"
                animate="enter"
                exit="exit"
                className="step-content"
              >
                <div className="step-header">
                  <h3>Final Review</h3>
                  <p className="subtitle">Verify the details before submitting the request.</p>
                </div>

                <div className="glass-summary-card">
                  <div className="summary-main">
                    <div className="summary-item">
                      <span className="label">Category</span>
                      <span className="value">{currentService?.category}</span>
                    </div>
                    {isMarketplaceFlow && selectedVendor && (
                       <div className="summary-item">
                         <span className="label">Partner Vendor</span>
                         <span className="value">{vendors.find(v => v.id === selectedVendor)?.name}</span>
                       </div>
                    )}
                    <div className="summary-item">
                      <span className="label">Location</span>
                      <span className="value">City Care Hospital</span>
                    </div>
                    <div className="summary-item">
                      <span className="label">Staff Count</span>
                      <span className="value">{workerCount} Professional(s)</span>
                    </div>
                  </div>
                  <div className="summary-footer">
                    <div className="price-estimation">
                      <span className="est-label">Estimated Rate</span>
                      <span className="est-value">
                         {isMarketplaceFlow && selectedVendor ? vendors.find(v => v.id === selectedVendor).price : currentService?.basePrice}
                         <small> /hour</small>
                      </span>
                    </div>
                  </div>
                </div>

                <div className="policy-note">
                  <Shield size={16} className="note-icon" />
                  <p>Invoices are generated upon completion based on verified logged hours.</p>
                </div>
              </motion.div>
            )}

            {(isSubmitting || isSuccess) && (
              <motion.div 
                key="success-state"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="step-content"
                style={{ textAlign: 'center', padding: '60px 20px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}
              >
                {!isSuccess ? (
                   <>
                     <div className="dot" style={{ width: '48px', height: '48px', background: 'var(--primary)', marginBottom: '16px' }}></div>
                     <h3 style={{ fontSize: '24px', fontWeight: '800' }}>Confirming Details...</h3>
                     <p className="subtitle">Securely placing your request over the Altus network.</p>
                   </>
                ) : (
                   <>
                     <div style={{ color: '#10B981', background: 'rgba(16, 185, 129, 0.1)', padding: '16px', borderRadius: '50%', marginBottom: '16px' }}>
                       <Sparkles size={48} />
                     </div>
                     <h3 style={{ fontSize: '24px', fontWeight: '800' }}>Service Requested!</h3>
                     <p className="subtitle">Your booking has been confirmed and placed in the queue.</p>
                   </>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {!isSubmitting && !isSuccess && (
          <div className="wizard-footer">
            {step > 1 && (
              <button className="btn-ghost" onClick={() => setStep(step - 1)}>
                <ChevronLeft size={18} /> Back
              </button>
            )}
            <div className="flex-spacer" />
            <button 
              className="btn-primary-large" 
              onClick={() => step < totalSteps ? setStep(step + 1) : handleConfirmOrder()}
              disabled={(step === 1 && !selectedService) || (step === 2 && isMarketplaceFlow && !selectedVendor)}
            >
              {step === totalSteps ? 'Confirm Order' : 'Continue'}
              {step < totalSteps && <ChevronRight size={18} />}
            </button>
          </div>
        )}
      </motion.div>
    </div>
  );
};

export default BookingWizard;
