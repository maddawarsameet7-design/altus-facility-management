import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ShieldCheck, CreditCard, ChevronRight, CheckCircle2, Loader2, Lock } from 'lucide-react';

const PaymentCheckout = ({ request, onPaymentSuccess, onClose }) => {
  const [step, setStep] = useState('review'); // review -> processing -> success
  const amount = request.total_amount || 450;

  const handlePay = () => {
    setStep('processing');
    setTimeout(() => {
      setStep('success');
      setTimeout(() => {
        onPaymentSuccess({ 
          transaction_id: `TXN-${Math.random().toString(36).substr(2, 9).toUpperCase()}`,
          amount: amount
        });
      }, 2000);
    }, 2500);
  };

  return (
    <motion.div 
      className="modal-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <motion.div 
        className="checkout-pane hero-card"
        initial={{ y: 50, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        style={{ maxWidth: '400px', width: '90%', padding: '0', overflow: 'hidden' }}
      >
        <div className="checkout-header" style={{ padding: '24px', background: 'rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
           <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Lock size={14} color="var(--accent-green)" />
              <span style={{ fontSize: '12px', fontWeight: '700', textTransform: 'uppercase', color: 'var(--accent-green)' }}>Secure Payment</span>
           </div>
           {step !== 'processing' && <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'white', cursor: 'pointer' }}>Close</button>}
        </div>

        <div className="checkout-content" style={{ padding: '32px 24px' }}>
          <AnimatePresence mode="wait">
            {step === 'review' && (
              <motion.div 
                key="review"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
              >
                <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: '14px', marginBottom: '4px' }}>Paying to Altsan Facility</p>
                <h2 style={{ fontSize: '32px', fontWeight: '800', marginBottom: '24px' }}>₹{amount}</h2>
                
                <div style={{ background: 'rgba(255,255,255,0.05)', borderRadius: '16px', padding: '16px', marginBottom: '32px' }}>
                   <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                      <span style={{ color: 'rgba(255,255,255,0.6)' }}>Service</span>
                      <span style={{ fontWeight: '600' }}>{request.service}</span>
                   </div>
                   <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'rgba(255,255,255,0.6)' }}>Request ID</span>
                      <span style={{ fontWeight: '600', fontSize: '12px' }}>#{request.id.substr(0,8)}</span>
                   </div>
                </div>

                <button className="primary-pay-btn" onClick={handlePay}>
                  Proceed to Pay <ChevronRight size={18} />
                </button>
              </motion.div>
            )}

            {step === 'processing' && (
              <motion.div 
                key="processing"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                style={{ textAlign: 'center', padding: '40px 0' }}
              >
                <Loader2 size={48} className="spinner" style={{ margin: '0 auto 24px', color: 'var(--accent-blue)' }} />
                <h3 style={{ fontSize: '20px', fontWeight: '700' }}>Processing Payment</h3>
                <p style={{ color: 'rgba(255,255,255,0.6)', marginTop: '8px' }}>Please do not refresh or close the app</p>
              </motion.div>
            )}

            {step === 'success' && (
              <motion.div 
                key="success"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                style={{ textAlign: 'center', padding: '40px 0' }}
              >
                <div style={{ width: 80, height: 80, background: 'var(--accent-green)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 24px' }}>
                  <CheckCircle2 size={48} color="white" />
                </div>
                <h3 style={{ fontSize: '24px', fontWeight: '800' }}>Payment Successful</h3>
                <p style={{ color: 'rgba(255,255,255,0.6)', marginTop: '8px' }}>Transaction ID: TXN-4920192</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div style={{ padding: '16px', textAlign: 'center', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
           <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', opacity: 0.5 }}>
              <ShieldCheck size={14} />
              <span style={{ fontSize: '10px', fontWeight: '700', textTransform: 'uppercase' }}>PCI-DSS Level 1 Encrypted</span>
           </div>
        </div>
      </motion.div>
    </motion.div>
  );
};

export default PaymentCheckout;
