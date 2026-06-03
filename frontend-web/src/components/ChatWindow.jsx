import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, X, User, MessageCircle } from 'lucide-react';

const ChatWindow = ({ request, currentUser, messages, onSendMessage, onClose }) => {
  const [text, setText] = useState('');
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    onSendMessage(text);
    setText('');
  };

  return (
    <motion.div 
      className="chat-overlay"
      initial={{ y: '100%' }}
      animate={{ y: 0 }}
      exit={{ y: '100%' }}
      transition={{ type: 'spring', damping: 25, stiffness: 200 }}
    >
      <div className="chat-container auth-glass-pane">
        <div className="chat-header">
           <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div className="chat-icon-bg">
                <MessageCircle size={20} color="white" />
              </div>
              <div>
                <h3 style={{ fontSize: '16px', fontWeight: '700' }}>{request.service} Chat</h3>
                <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.6)' }}>Issue: {request.issue || 'Facility Request'}</p>
              </div>
           </div>
           <button onClick={onClose} className="chat-close-btn">
             <X size={20} />
           </button>
        </div>

        <div className="chat-messages" ref={scrollRef}>
          {messages.length === 0 ? (
            <div className="empty-chat">
              <p>Start a conversation with the provider</p>
            </div>
          ) : (
            messages.map((msg, idx) => {
              const isMe = msg.sender_name === currentUser;
              return (
                <div key={msg.id || idx} className={`msg-wrapper ${isMe ? 'me' : 'them'}`}>
                  <div className="msg-bubble">
                    <p className="msg-content">{msg.content}</p>
                    <span className="msg-time">
                      {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        <form onSubmit={handleSend} className="chat-input-area">
          <input 
            type="text" 
            placeholder="Type a message..."
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <button type="submit" disabled={!text.trim()}>
            <Send size={18} />
          </button>
        </form>
      </div>
    </motion.div>
  );
};

export default ChatWindow;
