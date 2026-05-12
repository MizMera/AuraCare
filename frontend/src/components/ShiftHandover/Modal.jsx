import React from 'react';

const Modal = ({ isOpen, onClose, onConfirm, title, message }) => {
  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    }} onClick={onClose}>
      <div style={{
        backgroundColor: 'white',
        borderRadius: '12px',
        padding: '24px',
        width: '320px',
        maxWidth: '90%',
        boxShadow: '0 10px 40px rgba(0,0,0,0.2)',
        animation: 'slideIn 0.2s ease'
      }} onClick={(e) => e.stopPropagation()}>
        <h3 style={{
          margin: '0 0 12px 0',
          color: 'var(--midnight-green)',
          fontSize: '18px'
        }}>
          {title || 'Confirmation'}
        </h3>
        <p style={{
          margin: '0 0 24px 0',
          color: 'var(--text-dark)',
          fontSize: '14px',
          lineHeight: 1.5
        }}>
          {message || 'Are you sure you want to delete this report?'}
        </p>
        <div style={{
          display: 'flex',
          gap: '12px',
          justifyContent: 'flex-end'
        }}>
          <button
            onClick={onClose}
            style={{
              padding: '8px 20px',
              backgroundColor: 'transparent',
              border: '1px solid #D7E3EA',
              borderRadius: '8px',
              cursor: 'pointer',
              color: 'var(--midnight-green)',
              fontWeight: 500,
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => e.target.style.backgroundColor = '#F9FCFE'}
            onMouseLeave={(e) => e.target.style.backgroundColor = 'transparent'}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            style={{
              padding: '8px 20px',
              backgroundColor: '#dc3545',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer',
              color: 'white',
              fontWeight: 500,
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => e.target.style.backgroundColor = '#c82333'}
            onMouseLeave={(e) => e.target.style.backgroundColor = '#dc3545'}
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
};

export default Modal;