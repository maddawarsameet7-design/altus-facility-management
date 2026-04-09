import React, { useState } from 'react';
import './RatingModal.css';

const RatingModal = ({ booking, workerName, onClose, onSubmit }) => {
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [comment, setComment] = useState('');

  const handleRatingSubmit = () => {
    if (rating === 0) return;
    onSubmit({ rating, comment, bookingId: booking.id });
  };

  return (
    <div className="overlay">
      <div className="rating-modal">
        <button className="btn-close" onClick={onClose}>×</button>
        
        <div className="modal-header">
          <div className="success-icon">✨</div>
          <h2>Service Completed!</h2>
          <p>How was your experience with <strong>{workerName}</strong>?</p>
        </div>

        <div className="star-rating">
          {[...Array(5)].map((_, index) => {
            const starValue = index + 1;
            return (
              <button
                key={index}
                className={`star-btn ${starValue <= (hover || rating) ? 'active' : ''}`}
                onClick={() => setRating(starValue)}
                onMouseEnter={() => setHover(starValue)}
                onMouseLeave={() => setHover(0)}
              >
                ★
              </button>
            );
          })}
        </div>

        <div className="feedback-area">
          <label>Leave a comment (Optional)</label>
          <textarea 
            placeholder="What did they do well? etc."
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
        </div>

        <button 
          className="btn-submit-review" 
          disabled={rating === 0}
          onClick={handleRatingSubmit}
        >
          Submit Review
        </button>
      </div>
    </div>
  );
};

export default RatingModal;
