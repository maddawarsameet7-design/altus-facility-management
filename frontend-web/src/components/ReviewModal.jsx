import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Star, X, Check, ThumbsUp, Sparkles } from 'lucide-react';
import './ReviewModal.css';

const ReviewModal = ({ request, onClose, onSubmit }) => {
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [comment, setComment] = useState('');
  const [selectedTags, setSelectedTags] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  const quickTags = [
    "On Time", "Clean Work", "Polite", "Expert", "Went Extra Mile"
  ];

  const handleTagToggle = (tag) => {
    if (selectedTags.includes(tag)) {
      setSelectedTags(selectedTags.filter(t => t !== tag));
    } else {
      setSelectedTags([...selectedTags, tag]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (rating === 0) return alert("Please select a star rating.");
    
    setIsSubmitting(true);
    
    // Combine tags into comment if any
    const finalComment = selectedTags.length > 0 
      ? `[Tags: ${selectedTags.join(', ')}] ${comment}`
      : comment;

    const reviewData = {
      request: request.id,
      rating,
      comment: finalComment
    };
    
    if (request.worker) {
      reviewData.reviewee = request.assignments?.[0]?.worker?.user?.id || request.worker.id;
    }
    
    // Simulate slight delay for success animation
    setTimeout(async () => {
      setShowSuccess(true);
      setTimeout(async () => {
        await onSubmit(reviewData);
        setIsSubmitting(false);
      }, 1500);
    }, 800);
  };

  return (
    <motion.div 
      className="review-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <motion.div 
        className="review-sheet"
        initial={{ y: '100%' }}
        animate={{ y: 0 }}
        exit={{ y: '100%' }}
        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
      >
        <div className="sheet-handle"></div>
        
        <button className="sheet-close-btn" onClick={onClose}>
          <X size={20} />
        </button>

        <AnimatePresence mode="wait">
          {!showSuccess ? (
            <motion.div 
              key="form"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="review-content-wrapper"
            >
              <div className="review-header">
                <div className="review-icon-circle">
                  <Sparkles size={28} className="text-orange" />
                </div>
                <h2>Rate the Service</h2>
                <p>How was your experience with the {request.service}?</p>
              </div>

              <form onSubmit={handleSubmit} className="review-form">
                <div className="star-rating-container">
                  {[1, 2, 3, 4, 5].map((index) => (
                    <motion.button
                      type="button"
                      key={index}
                      className={`star-btn ${index <= (hover || rating) ? 'active' : ''}`}
                      onClick={() => setRating(index)}
                      onMouseEnter={() => setHover(index)}
                      onMouseLeave={() => setHover(0)}
                      whileTap={{ scale: 0.8 }}
                      animate={index <= rating ? { scale: [1, 1.2, 1] } : { scale: 1 }}
                      transition={{ duration: 0.3 }}
                    >
                      <Star 
                        size={40} 
                        fill={index <= (hover || rating) ? 'var(--accent-orange)' : 'transparent'} 
                        className={index <= (hover || rating) ? 'star-filled' : 'star-empty'}
                      />
                    </motion.button>
                  ))}
                </div>

                <div className="quick-tags">
                  {quickTags.map(tag => (
                    <button 
                      type="button" 
                      key={tag}
                      className={`tag-chip ${selectedTags.includes(tag) ? 'selected' : ''}`}
                      onClick={() => handleTagToggle(tag)}
                    >
                      {tag}
                    </button>
                  ))}
                </div>

                <div className="input-group">
                  <textarea 
                    className="review-textarea"
                    placeholder="Share additional feedback (optional)..."
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    rows={3}
                  />
                </div>

                <button 
                  type="submit" 
                  className={`review-submit-btn ${rating > 0 ? 'active' : ''}`} 
                  disabled={isSubmitting || rating === 0}
                >
                  {isSubmitting ? <div className="spinner-small"></div> : 'Submit Feedback'}
                </button>
              </form>
            </motion.div>
          ) : (
            <motion.div 
              key="success"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              className="review-success-state"
            >
              <motion.div 
                className="success-icon-wrap"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 200, damping: 15 }}
              >
                <ThumbsUp size={48} color="white" />
              </motion.div>
              <h3>Thank You!</h3>
              <p>Your feedback helps us improve Altsan services.</p>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </motion.div>
  );
};

export default ReviewModal;
