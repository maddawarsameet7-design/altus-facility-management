import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Star, X, Check } from 'lucide-react';

const ReviewModal = ({ request, onClose, onSubmit }) => {
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [comment, setComment] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (rating === 0) return alert("Please select a star rating.");
    
    setIsSubmitting(true);
    const reviewData = {
      request: request.id,
      rating,
      comment
    };
    // If there's an assigned worker, set them as reviewee
    if (request.worker) {
      // The worker object from the mapped data has user info nested
      reviewData.reviewee = request.assignments?.[0]?.worker?.user?.id || request.worker.id;
    }
    await onSubmit(reviewData);
    setIsSubmitting(false);
  };

  return (
    <motion.div 
      className="modal-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <motion.div 
        className="auth-glass-pane review-pane"
        initial={{ scale: 0.9, opacity: 0, y: 20 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.9, opacity: 0, y: 20 }}
      >
        <button className="modal-close-btn" onClick={onClose}>
          <X size={20} />
        </button>

        <div className="review-header">
           <div className="review-icon-circle">
             <Star size={32} fill="var(--accent-orange)" color="var(--accent-orange)" />
           </div>
           <h2>Rate the Service</h2>
           <p>How was your experience with the {request.service}?</p>
        </div>

        <form onSubmit={handleSubmit} className="review-form">
          <div className="star-rating-container">
            {[1, 2, 3, 4, 5].map((index) => (
              <button
                type="button"
                key={index}
                className={`star-btn ${index <= (hover || rating) ? 'active' : ''}`}
                onClick={() => setRating(index)}
                onMouseEnter={() => setHover(index)}
                onMouseLeave={() => setHover(0)}
              >
                <Star 
                  size={32} 
                  fill={index <= (hover || rating) ? 'var(--accent-orange)' : 'transparent'} 
                />
              </button>
            ))}
          </div>

          <div className="input-group">
            <label>Share your feedback (optional)</label>
            <textarea 
              placeholder="Tell us what went well or how we can improve..."
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={4}
            />
          </div>

          <button type="submit" className="btn-auth-submit" disabled={isSubmitting}>
            {isSubmitting ? <div className="spinner"></div> : 'Submit Feedback'}
          </button>
        </form>
      </motion.div>
    </motion.div>
  );
};

export default ReviewModal;
