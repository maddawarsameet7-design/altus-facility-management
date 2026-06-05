import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ShieldCheck, ChevronRight, CheckCircle2, Loader2, Lock, CreditCard, Apple, Smartphone, Fingerprint } from 'lucide-react';
import { paymentApi } from '../utils/api';
import './PaymentCheckout.css';

const PaymentCheckout = ({ request, onPaymentSuccess, onClose }) => {
  const [step, setStep] = useState('review'); // review -> auth -> processing -> success
  const amount = request.total_amount || 450;

  const handlePay = async () => {
    setStep('processing');
    try {
      // 1. Create Order on Django Backend
      const orderRes = await paymentApi.createOrder({
        request_id: request.id,
        amount: amount
      });
      const orderData = orderRes.data;

      // 2. Initialize Razorpay Options
      const options = {
        key: orderData.key,
        amount: orderData.amount,
        currency: orderData.currency,
        name: "Altsan Facility Services",
        description: `Payment for Request #${request.id}`,
        order_id: orderData.order_id,
        handler: async function (response) {
          try {
            // 3. Verify Payment Signature on Backend
            await paymentApi.verify({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
              request_id: request.id
            });
            setStep('success');
            setTimeout(() => {
              onPaymentSuccess({ 
                transaction_id: response.razorpay_payment_id,
                amount: amount
              });
            }, 2000);
          } catch (err) {
            console.error("Signature verification failed", err);
            setStep('review');
            alert("Payment verification failed. Please contact support.");
          }
        },
        prefill: {
          name: "Resident",
          email: "resident@altsan.com",
          contact: "9999999999"
        },
        theme: {
          color: "#000000"
        },
        modal: {
          ondismiss: function() {
            setStep('review');
          }
        }
      };

      const rzp = new window.Razorpay(options);
      rzp.on('payment.failed', function (response){
        console.error("Payment Failed", response.error);
        setStep('review');
        alert(`Payment failed: ${response.error.description}`);
      });
      rzp.open();
    } catch (err) {
      console.error("Order creation failed", err);
      setStep('review');
      alert("Could not initialize payment. Please try again.");
    }
  };

  return (
    <motion.div 
      className="checkout-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <motion.div 
        className="checkout-sheet"
        initial={{ y: '100%' }}
        animate={{ y: 0 }}
        exit={{ y: '100%' }}
        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
      >
        <div className="sheet-handle"></div>

        <div className="checkout-header">
           <div className="header-brand">
              <div className="secure-badge">
                <Lock size={12} className="text-green" />
              </div>
              <span>Secure Checkout</span>
           </div>
           {step === 'review' && <button onClick={onClose} className="close-sheet-btn">Cancel</button>}
        </div>

        <div className="checkout-content">
          <AnimatePresence mode="wait">
            {step === 'review' && (
              <motion.div 
                key="review"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="step-review"
              >
                <div className="amount-display">
                  <p>Altsan Facility Services</p>
                  <h2>₹{amount.toLocaleString('en-IN')}</h2>
                </div>

                <div className="virtual-card-wrapper">
                  <div className="virtual-card">
                    <div className="card-top">
                      <CreditCard size={24} color="rgba(255,255,255,0.8)" />
                      <span className="card-type">VISA</span>
                    </div>
                    <div className="card-chip"></div>
                    <div className="card-number">
                      <span>****</span><span>****</span><span>****</span><span>4242</span>
                    </div>
                    <div className="card-bottom">
                      <div className="card-holder">SAMEET MADDAWAR</div>
                      <div className="card-expiry">12/28</div>
                    </div>
                  </div>
                </div>

                <div className="order-summary">
                   <div className="summary-row">
                      <span className="label">Service</span>
                      <span className="value">{request.service}</span>
                   </div>
                   <div className="summary-row">
                      <span className="label">Request ID</span>
                      <span className="value">#{request.id.substr(0,8)}</span>
                   </div>
                   <div className="summary-divider"></div>
                   <div className="summary-row total">
                      <span className="label">Total to Pay</span>
                      <span className="value">₹{amount.toLocaleString('en-IN')}</span>
                   </div>
                </div>

                <button className="apple-pay-btn" onClick={handlePay}>
                  <Apple size={18} fill="currentColor" style={{marginRight: '6px'}}/> Pay
                </button>

                <button className="primary-pay-btn" onClick={handlePay}>
                  Pay with Card <ChevronRight size={18} />
                </button>
              </motion.div>
            )}

            {step === 'auth' && (
              <motion.div 
                key="auth"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="step-auth"
              >
                <div className="auth-scanner">
                  <Fingerprint size={64} className="fingerprint-icon scanning" />
                  <div className="scan-line"></div>
                </div>
                <h3>Authenticate Payment</h3>
                <p>Verify your identity to proceed</p>
              </motion.div>
            )}

            {step === 'processing' && (
              <motion.div 
                key="processing"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="step-processing"
              >
                <div className="spinner-ring">
                  <Loader2 size={48} className="spinner" />
                </div>
                <h3>Processing Payment</h3>
                <p>Contacting your bank securely...</p>
              </motion.div>
            )}

            {step === 'success' && (
              <motion.div 
                key="success"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="step-success"
              >
                <motion.div 
                  className="success-circle"
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: "spring", stiffness: 200, damping: 20 }}
                >
                  <CheckCircle2 size={48} color="white" />
                </motion.div>
                <h3>Payment Successful</h3>
                <p>Transaction ID: TXN-{Math.random().toString(36).substr(2, 9).toUpperCase()}</p>
                
                <div className="receipt-pill">
                  Receipt sent to your email
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="checkout-footer">
           <div className="security-badges">
              <ShieldCheck size={14} />
              <span>PCI-DSS Level 1 Encrypted</span>
           </div>
        </div>
      </motion.div>
    </motion.div>
  );
};

export default PaymentCheckout;
