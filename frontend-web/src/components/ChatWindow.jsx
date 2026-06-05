import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, X, MessageCircle, Paperclip, CheckCheck, User } from 'lucide-react';
import './ChatWindow.css';

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
      className="premium-chat-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <motion.div 
        className="premium-chat-container"
        initial={{ y: '100%', scale: 0.95 }}
        animate={{ y: 0, scale: 1 }}
        exit={{ y: '100%', scale: 0.95 }}
        transition={{ type: 'spring', damping: 25, stiffness: 250 }}
      >
        <header className="chat-glass-header">
           <div className="header-left">
              <div className="chat-avatar">
                <User size={20} className="text-blue" />
                <span className="online-dot"></span>
              </div>
              <div className="header-info">
                <h3>{request.service} Chat</h3>
                <p>Provider is online</p>
              </div>
           </div>
           <button onClick={onClose} className="chat-close-btn">
             <X size={20} />
           </button>
        </header>

        <div className="chat-scroll-area" ref={scrollRef}>
          <div className="chat-date-divider"><span>Today</span></div>
          
          <AnimatePresence>
            {messages.length === 0 ? (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="empty-chat-state">
                <div className="empty-icon-wrap"><MessageCircle size={32} /></div>
                <p>This is the beginning of your conversation.</p>
              </motion.div>
            ) : (
              messages.map((msg, idx) => {
                const isMe = msg.sender_name === currentUser;
                return (
                  <motion.div 
                    key={msg.id || idx} 
                    className={`chat-bubble-wrapper ${isMe ? 'is-me' : 'is-them'}`}
                    initial={{ opacity: 0, y: 10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    transition={{ type: 'spring', stiffness: 300, damping: 25 }}
                  >
                    <div className="chat-bubble">
                      <p className="bubble-text">{msg.content}</p>
                      <div className="bubble-meta">
                        <span className="bubble-time">
                          {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                        {isMe && <CheckCheck size={14} className="read-receipt" />}
                      </div>
                    </div>
                  </motion.div>
                );
              })
            )}
          </AnimatePresence>
        </div>

        <div className="chat-input-wrapper">
          <button type="button" className="attachment-btn">
            <Paperclip size={20} />
          </button>
          <form onSubmit={handleSend} className="chat-input-form">
            <input 
              type="text" 
              placeholder="iMessage"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <button type="submit" className={`send-btn ${text.trim() ? 'active' : ''}`} disabled={!text.trim()}>
              <Send size={18} />
            </button>
          </form>
        </div>
      </motion.div>
    </motion.div>
  );
};

export default ChatWindow;
