// src/components/NotificationBell.jsx
import { useState, useEffect, useRef } from 'react';
import { Bell, BellRing, X, Volume2, VolumeX, CheckCheck } from 'lucide-react';
import { notificationService } from '../services/mealService';
import { useNotificationSound } from '../hooks/useNotificationSound';

export default function NotificationBell({ token, onUnreadCountChange }) {
  const [notifications, setNotifications] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const dropdownRef = useRef(null);
  
  const { playSound, toggleSound, isEnabled } = useNotificationSound();

  // Charger les IDs déjà joués depuis localStorage
  const getPlayedIds = () => {
    const saved = localStorage.getItem('playedNotificationIds');
    return saved ? new Set(JSON.parse(saved)) : new Set();
  };

  // Sauvegarder les IDs joués
  const savePlayedIds = (idsSet) => {
    localStorage.setItem('playedNotificationIds', JSON.stringify([...idsSet]));
  };

  const playedIdsRef = useRef(getPlayedIds());

  const fetchNotifications = async () => {
    try {
      const data = await notificationService.getAll(true);
      
      // Trouver les nouvelles notifications (IDs non joués)
      const newNotifications = data.filter(notif => !playedIdsRef.current.has(notif.id));
      
      // Jouer le son pour chaque nouvelle notification (une seule fois)
      if (newNotifications.length > 0 && isEnabled) {
        newNotifications.forEach(() => {
          playSound();
        });
        // Ajouter les IDs au Set
        newNotifications.forEach(notif => {
          playedIdsRef.current.add(notif.id);
        });
        savePlayedIds(playedIdsRef.current);
      }
      
      setNotifications(data);
      setUnreadCount(data.length);
      if (onUnreadCountChange) {
        onUnreadCountChange(data.length);
      }
    } catch (err) {
      console.error('Failed to fetch notifications', err);
    }
  };

  const handleMarkAsRead = async (id) => {
    await notificationService.markAsRead(id);
    // On garde l'ID dans le Set (pour ne pas rejouer le son si elle revient)
    fetchNotifications();
  };

  const handleMarkAllAsRead = async () => {
    await notificationService.markAllAsRead();
    fetchNotifications();
  };

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 10000);
    return () => clearInterval(interval);
  }, [isEnabled]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getNotificationColor = (type) => {
    switch(type) {
      case 'INCIDENT': return '#EF4444';
      case 'ABSENCE': return '#F59E0B';
      case 'HEALTH': return '#10B981';
      default: return '#8B5CF6';
    }
  };

  const getNotificationIcon = (type) => {
    switch(type) {
      case 'INCIDENT': return '🚨';
      case 'ABSENCE': return '⚠️';
      case 'HEALTH': return '💚';
      default: return '📢';
    }
  };

  return (
    <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: '0.5rem' }} ref={dropdownRef}>
      <button
        onClick={toggleSound}
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '8px',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'all 0.2s'
        }}
        title={isEnabled ? 'Désactiver le son' : 'Activer le son'}
      >
        {isEnabled ? (
          <Volume2 size={18} color="rgba(255,255,255,0.7)" />
        ) : (
          <VolumeX size={18} color="rgba(255,255,255,0.5)" />
        )}
      </button>

      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          position: 'relative',
          padding: '10px',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'all 0.2s ease',
          backgroundColor: isOpen ? 'rgba(255,255,255,0.1)' : 'transparent'
        }}
      >
        {unreadCount > 0 ? (
          <>
            <BellRing size={22} color="#F59E0B" />
            <span style={{
              position: 'absolute',
              top: 0,
              right: 0,
              backgroundColor: '#EF4444',
              color: 'white',
              borderRadius: '50%',
              width: '20px',
              height: '20px',
              fontSize: '11px',
              fontWeight: 'bold',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              animation: 'pulse 1s infinite'
            }}>
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          </>
        ) : (
          <Bell size={22} color="rgba(255,255,255,0.6)" />
        )}
      </button>

      {isOpen && (
        <>
          <style>{`
            @keyframes slideIn {
              from {
                opacity: 0;
                transform: translateY(-10px);
              }
              to {
                opacity: 1;
                transform: translateY(0);
              }
            }
            @keyframes pulse {
              0%, 100% { transform: scale(1); }
              50% { transform: scale(1.1); }
            }
          `}</style>
          <div style={{
            position: 'absolute',
            bottom: '60px',
            left: 0,
            width: '420px',
            maxHeight: '500px',
            backgroundColor: 'white',
            borderRadius: '16px',
            boxShadow: '0 20px 60px rgba(0,0,0,0.2)',
            zIndex: 1000,
            overflow: 'hidden',
            animation: 'slideIn 0.2s ease'
          }}>
            <div style={{
              padding: '1rem 1.5rem',
              borderBottom: '1px solid #E5E7EB',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              background: 'linear-gradient(135deg, #1E3A5F 0%, #0F2B44 100%)',
              color: 'white'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <BellRing size={18} />
                <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: '600' }}>Notifications</h3>
              </div>
              {unreadCount > 0 && (
                <button
                  onClick={handleMarkAllAsRead}
                  style={{
                    background: 'rgba(255,255,255,0.2)',
                    border: 'none',
                    color: 'white',
                    cursor: 'pointer',
                    padding: '6px 12px',
                    borderRadius: '8px',
                    fontSize: '0.75rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.3rem',
                    transition: 'all 0.2s'
                  }}
                  onMouseEnter={(e) => e.target.style.backgroundColor = 'rgba(255,255,255,0.3)'}
                  onMouseLeave={(e) => e.target.style.backgroundColor = 'rgba(255,255,255,0.2)'}
                >
                  <CheckCheck size={14} /> Tout lire
                </button>
              )}
            </div>

            <div style={{ maxHeight: '440px', overflowY: 'auto', padding: '0.5rem' }}>
              {notifications.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '3rem', color: '#9CA3AF' }}>
                  <Bell size={32} style={{ marginBottom: '0.5rem', opacity: 0.5 }} />
                  <p style={{ margin: 0, fontSize: '0.9rem' }}>Aucune notification</p>
                  <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.75rem' }}>Les alertes apparaîtront ici</p>
                </div>
              ) : (
                notifications.map(notif => (
                  <div
                    key={notif.id}
                    onClick={() => handleMarkAsRead(notif.id)}
                    style={{
                      padding: '1rem',
                      marginBottom: '0.5rem',
                      borderRadius: '12px',
                      borderLeft: `4px solid ${getNotificationColor(notif.notification_type)}`,
                      backgroundColor: notif.is_read ? '#F9FAFB' : '#FFF7ED',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                      transition: 'all 0.2s ease',
                      cursor: 'pointer'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.transform = 'translateX(4px)'}
                    onMouseLeave={(e) => e.currentTarget.style.transform = 'translateX(0)'}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                          <span style={{ fontSize: '1.2rem' }}>
                            {getNotificationIcon(notif.notification_type)}
                          </span>
                          <strong style={{
                            color: getNotificationColor(notif.notification_type),
                            fontSize: '0.75rem',
                            textTransform: 'uppercase',
                            letterSpacing: '0.5px'
                          }}>
                            {notif.notification_type === 'ABSENCE' ? 'ABSENCE DÉTECTÉE' : 
                             notif.notification_type === 'INCIDENT' ? 'INCIDENT' : 'INFORMATION'}
                          </strong>
                          {!notif.is_read && (
                            <span style={{
                              backgroundColor: '#EF4444',
                              color: 'white',
                              fontSize: '0.65rem',
                              padding: '2px 8px',
                              borderRadius: '20px'
                            }}>
                              Nouveau
                            </span>
                          )}
                        </div>
                        <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.85rem', color: '#1F2937', lineHeight: '1.4' }}>
                          {notif.message}
                        </p>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                          <small style={{ color: '#9CA3AF', fontSize: '0.65rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                            🕐 {new Date(notif.created_at).toLocaleTimeString()}
                          </small>
                          <small style={{ color: '#9CA3AF', fontSize: '0.65rem' }}>
                            📅 {new Date(notif.created_at).toLocaleDateString()}
                          </small>
                        </div>
                      </div>
                      {!notif.is_read && (
                        <button
                          onClick={(e) => { e.stopPropagation(); handleMarkAsRead(notif.id); }}
                          style={{
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            color: '#9CA3AF',
                            fontSize: '11px',
                            padding: '4px 8px',
                            borderRadius: '6px',
                            transition: 'all 0.2s'
                          }}
                          onMouseEnter={(e) => {
                            e.target.style.backgroundColor = '#F3F4F6';
                            e.target.style.color = '#1E3A5F';
                          }}
                          onMouseLeave={(e) => {
                            e.target.style.backgroundColor = 'transparent';
                            e.target.style.color = '#9CA3AF';
                          }}
                        >
                          ✓ Marquer lue
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}