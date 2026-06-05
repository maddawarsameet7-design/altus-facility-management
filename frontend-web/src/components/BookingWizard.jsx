import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import useStore from '../store/useStore';
import { categoryApi } from '../utils/api';
import { 
  Sparkles, Shield, Zap, Droplets, ChevronRight, ChevronLeft, X,
  Calendar, Clock, Building2, Users, Award, Star, Leaf, Trash2,
  FileText, CheckCircle2
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
  return map[name] || { icon: FileText, color: '#9CA3AF', roles: ['member'] };
};

const locations = ['Block A Lobby', 'Block B Corridor', 'Main Gate', 'Resident Flat'];

const BookingWizard = ({ onClose, onSuccess, currentRole }) => {
  const [step, setStep] = useState(1);
  const [services, setServices] = useState([]);
  const [selectedService, setSelectedService] = useState(null);
  const [selectedVendor, setSelectedVendor] = useState(null);
  const [selectedLocation, setSelectedLocation] = useState('Block A Lobby');
  const [workerCount, setWorkerCount] = useState(1);
  
  const { services: rawServices, servicesLoading: loading, fetchServices } = useStore();
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  useEffect(() => {
    fetchServices();
  }, [fetchServices]);

  // Enrich the raw services with our UI styles
  const services = rawServices.map(cat => ({
    ...cat,
    category: cat.name,
    ...getStyleForCategory(cat.name),
    basePrice: `₹${cat.base_hourly_rate}/hr`
  }));
  
  const currentService = services.find(s => s.id === selectedService);
  const isMarketplaceFlow = currentService?.category === 'Housekeeping';
  const totalSteps = isMarketplaceFlow ? 4 : 3;

  const handleConfirmOrder = () => {
    setIsSubmitting(true);
    setTimeout(() => {
      setIsSubmitting(false);
      setIsSuccess(true);
      setTimeout(() => {
        onSuccess(currentService);
      }, 2000);
    }, 1500);
  };

  const drawerVariants = {
    hidden: { y: "100%", opacity: 0 },
    visible: { y: 0, opacity: 1, transition: { type: "spring", damping: 25, stiffness: 200 } },
    exit: { y: "100%", opacity: 0, transition: { duration: 0.3 } }
  };

  const stepVariants = {
    initial: { x: 20, opacity: 0 },
    enter: { x: 0, opacity: 1, transition: { duration: 0.4, ease: "easeOut" } },
    exit: { x: -20, opacity: 0, transition: { duration: 0.3, ease: "easeIn" } }
  };

  const listVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.1 } }
  };
  
  const itemVariants = {
    hidden: { y: 20, opacity: 0 },
    visible: { y: 0, opacity: 1 }
  };

  return (
    <div className="drawer-overlay">
      <div className="drawer-backdrop" onClick={onClose} />
      
      <motion.div 
        className="drawer-container dark-glass-theme"
        variants={drawerVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
      >
        <div className="drawer-handle" />
        <button type="button" className="drawer-close-btn" onClick={onClose}>
          <X size={20} />
        </button>
        
        <div className="drawer-header">
          <h2>Book a Service</h2>
          <div className="modern-progress">
            {Array.from({ length: totalSteps }).map((_, idx) => (
              <div key={idx} className={`progress-segment ${step > idx ? 'active' : ''} ${step === idx + 1 ? 'current' : ''}`} />
            ))}
          </div>
        </div>

        <div className="drawer-body">
          <AnimatePresence mode="wait">
            {step === 1 && (
              <motion.div key="step1" variants={stepVariants} initial="initial" animate="enter" exit="exit" className="step-content">
                <div className="step-title-area">
                  <h3>Select Category</h3>
                  <p>What kind of professional do you need?</p>
                </div>
                
                <motion.div className="premium-services-grid" variants={listVariants} initial="hidden" animate="visible">
                  {services.filter(s => currentRole === 'chairman' ? s.roles.includes('chairman') : s.roles.includes('member')).map(service => {
                    const Icon = service.icon;
                    const isSelected = selectedService === service.id;
                    return (
                      <motion.div 
                        key={service.id}
                        variants={itemVariants}
                        whileTap={{ scale: 0.95 }}
                        className={`premium-service-card ${isSelected ? 'selected' : ''}`}
                        style={{ '--accent': service.color }}
                        onClick={() => setSelectedService(service.id)}
                      >
                        <div className="card-bg-glow" style={{ background: service.color }} />
                        <div className="p-icon-box" style={{ color: service.color }}>
                          <Icon size={32} />
                        </div>
                        <div className="p-info">
                          <h4>{service.category}</h4>
                          <span>from {service.basePrice}</span>
                        </div>
                        {isSelected && <div className="p-check"><CheckCircle2 size={20} fill={service.color} stroke="#111" /></div>}
                      </motion.div>
                    );
                  })}
                </motion.div>
              </motion.div>
            )}

            {step === 2 && isMarketplaceFlow && (
              <motion.div key="step-vendor" variants={stepVariants} initial="initial" animate="enter" exit="exit" className="step-content">
                <div className="step-title-area">
                  <h3>Select Partner</h3>
                  <p>Choose an elite vendor for your facility.</p>
                </div>
                
                <motion.div className="vip-vendor-list" variants={listVariants} initial="hidden" animate="visible">
                  {vendors.map(vendor => (
                    <motion.div 
                      key={vendor.id}
                      variants={itemVariants}
                      whileTap={{ scale: 0.98 }}
                      className={`vip-vendor-card ${selectedVendor === vendor.id ? 'selected' : ''}`}
                      onClick={() => setSelectedVendor(vendor.id)}
                    >
                      <div className="vip-avatar">
                        {(() => { const Icon = vendor.icon; return <Icon size={24} />; })()}
                      </div>
                      <div className="vip-details">
                        <h4>{vendor.name}</h4>
                        <p>{vendor.specialization}</p>
                      </div>
                      <div className="vip-stats">
                        <div className="vip-rating"><Star size={12} fill="#F59E0B" stroke="none" /> {vendor.rating}</div>
                        <div className="vip-price">{vendor.price}</div>
                      </div>
                    </motion.div>
                  ))}
                </motion.div>
              </motion.div>
            )}

            {step === (isMarketplaceFlow ? 3 : 2) && (
              <motion.div key="step-schedule" variants={stepVariants} initial="initial" animate="enter" exit="exit" className="step-content">
                <div className="step-title-area">
                  <h3>Schedule & Details</h3>
                  <p>When and where do you need them?</p>
                </div>
                
                <div className="modern-form">
                  <div className="form-group">
                    <label><Calendar size={16} /> Date & Time</label>
                    <div className="input-split">
                      <input type="date" className="sleek-input" defaultValue={new Date().toISOString().split('T')[0]} />
                      <input type="time" className="sleek-input" defaultValue="09:00" />
                    </div>
                  </div>

                  <div className="form-group">
                    <label><Building2 size={16} /> Location</label>
                    <div className="touch-pill-grid">
                      {locations.map(loc => (
                        <div 
                          key={loc} 
                          className={`touch-pill ${selectedLocation === loc ? 'active' : ''}`}
                          onClick={() => setSelectedLocation(loc)}
                        >
                          {loc}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="form-group">
                    <label><Users size={16} /> Professional Count</label>
                    <div className="sleek-counter">
                      <button onClick={() => setWorkerCount(Math.max(1, workerCount - 1))}>-</button>
                      <span>{workerCount}</span>
                      <button onClick={() => setWorkerCount(workerCount + 1)}>+</button>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {step === totalSteps && !isSuccess && !isSubmitting && (
              <motion.div key="step-review" variants={stepVariants} initial="initial" animate="enter" exit="exit" className="step-content">
                <div className="step-title-area">
                  <h3>Review Order</h3>
                  <p>Your digital service receipt.</p>
                </div>

                <div className="digital-receipt">
                  <div className="receipt-header">
                    <div className="r-icon" style={{ color: currentService?.color }}>
                      {(() => { const Icon = currentService?.icon; return <Icon size={32} />; })()}
                    </div>
                    <div>
                      <h4>{currentService?.category}</h4>
                      <p>{workerCount} Professional(s)</p>
                    </div>
                  </div>
                  
                  <div className="receipt-body">
                    {isMarketplaceFlow && selectedVendor && (
                       <div className="r-row">
                         <span>Partner</span>
                         <strong>{vendors.find(v => v.id === selectedVendor)?.name}</strong>
                       </div>
                    )}
                    <div className="r-row">
                      <span>Location</span>
                      <strong>{selectedLocation}</strong>
                    </div>
                    <div className="r-row">
                      <span>Date & Time</span>
                      <strong>Today, 09:00 AM</strong>
                    </div>
                  </div>
                  
                  <div className="receipt-footer">
                    <span>Estimated Rate</span>
                    <div className="r-total">
                      {isMarketplaceFlow && selectedVendor ? vendors.find(v => v.id === selectedVendor).price : currentService?.basePrice}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {(isSubmitting || isSuccess) && (
              <motion.div 
                key="success-state"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="step-content center-success"
              >
                {!isSuccess ? (
                   <div className="processing-state">
                     <div className="glowing-spinner" />
                     <h3>Securing Request...</h3>
                     <p>Connecting to the Altsan network.</p>
                   </div>
                ) : (
                   <motion.div 
                     initial={{ scale: 0.8, opacity: 0 }} 
                     animate={{ scale: 1, opacity: 1 }} 
                     className="success-state"
                   >
                     <div className="success-icon-burst">
                       <CheckCircle2 size={64} color="#10B981" />
                     </div>
                     <h3>Order Confirmed!</h3>
                     <p>Professionals are en route to your location.</p>
                   </motion.div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {!isSubmitting && !isSuccess && (
          <div className="drawer-footer">
            <button 
              className="drawer-btn-back" 
              onClick={() => step > 1 ? setStep(step - 1) : onClose()}
            >
              {step > 1 ? 'Back' : 'Cancel'}
            </button>
            <button 
              className="drawer-btn-next" 
              onClick={() => step < totalSteps ? setStep(step + 1) : handleConfirmOrder()}
              disabled={(step === 1 && !selectedService) || (step === 2 && isMarketplaceFlow && !selectedVendor)}
            >
              {step === totalSteps ? 'Confirm' : 'Next'}
            </button>
          </div>
        )}
      </motion.div>
    </div>
  );
};

export default BookingWizard;
