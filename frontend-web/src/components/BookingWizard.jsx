import React, { useState } from 'react';
import './BookingWizard.css';

const services = [
  { id: 'srv-1', category: 'Housekeeping', icon: '🧹', basePrice: '$25/hr', description: 'Deep cleaning and maintenance for wards and office areas.' },
  { id: 'srv-2', category: 'Security Guard', icon: '🛡️', basePrice: '$30/hr', description: 'Trained professional security for access control.' },
  { id: 'srv-3', category: 'Electrician', icon: '⚡', basePrice: '$45/hr', description: 'Certified electrical repairs and installations.' },
  { id: 'srv-4', category: 'Plumber', icon: '🚰', basePrice: '$40/hr', description: 'Emergency leaks and scheduled plumbing maintenance.' }
];

const BookingWizard = () => {
  const [step, setStep] = useState(1);
  const [selectedService, setSelectedService] = useState(null);
  
  return (
    <div className="wizard-container">
      <div className="wizard-header">
        <h2>Book a Service</h2>
        <div className="progress-bar">
          <div className="progress-track">
            <div className={`progress-fill step-${step}`}></div>
          </div>
          <div className="steps-indicators">
            <span className={step >= 1 ? 'active' : ''}>Service</span>
            <span className={step >= 2 ? 'active' : ''}>Schedule</span>
            <span className={step >= 3 ? 'active' : ''}>Review</span>
          </div>
        </div>
      </div>

      <div className="wizard-body">
        {step === 1 && (
          <div className="step-content animate-fade-in">
            <h3>Select a Service Category</h3>
            <p className="subtitle">What type of professional do you need?</p>
            
            <div className="services-grid">
              {services.map(service => (
                <div 
                  key={service.id}
                  className={`service-card ${selectedService === service.id ? 'selected' : ''}`}
                  onClick={() => setSelectedService(service.id)}
                >
                  <div className="service-icon">{service.icon}</div>
                  <h4>{service.category}</h4>
                  <p className="service-desc">{service.description}</p>
                  <div className="service-price">From {service.basePrice}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="step-content animate-fade-in">
            <h3>Schedule & Details</h3>
            <p className="subtitle">When and where do you need the service?</p>
            
            <div className="form-group row">
              <div className="input-block">
                <label>Date</label>
                <input type="date" className="custom-input" />
              </div>
              <div className="input-block">
                <label>Time</label>
                <input type="time" className="custom-input" />
              </div>
            </div>

            <div className="form-group">
              <label>Select Property Facility</label>
              <select className="custom-input">
                <option>City Care Hospital - Main Building</option>
                <option>TechPark - Tower B</option>
              </select>
            </div>

            <div className="form-group">
              <label>Number of Workers Needed</label>
              <div className="counter-input">
                <button>-</button>
                <input type="number" readOnly value="1" />
                <button>+</button>
              </div>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="step-content animate-fade-in">
            <h3>Review & Confirm</h3>
            <div className="summary-card">
              <div className="summary-row">
                <span>Service:</span>
                <strong>{services.find(s => s.id === selectedService)?.category || 'None'}</strong>
              </div>
              <div className="summary-row">
                <span>Facility:</span>
                <strong>City Care Hospital - Main Building</strong>
              </div>
              <div className="summary-row">
                <span>Date & Time:</span>
                <strong>Tomorrow, 09:00 AM</strong>
              </div>
              <div className="divider"></div>
              <div className="summary-row total">
                <span>Estimated Total:</span>
                <strong>$120.00</strong>
              </div>
            </div>
            
            <div className="info-alert">
              ℹ️ A final invoice will be generated upon task completion. Payment will be deducted securely.
            </div>
          </div>
        )}
      </div>

      <div className="wizard-footer">
        {step > 1 && (
          <button className="btn-back" onClick={() => setStep(step - 1)}>
            Back
          </button>
        )}
        <div style={{ flex: 1 }}></div>
        <button 
          className="btn-next" 
          onClick={() => step < 3 ? setStep(step + 1) : alert('Booking Confirmed!')}
          disabled={step === 1 && !selectedService}
        >
          {step === 3 ? 'Confirm Booking' : 'Continue'}
        </button>
      </div>
    </div>
  );
};

export default BookingWizard;
