import { useState, useEffect, useRef } from 'react';
import { Bell, BellRing, X } from 'lucide-react';
import { notificationService } from '../services/mealService';

export default function NotificationBell() {
  const [notifications, setNotifications] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const dropdownRef = useRef(null);

  const fetchNotifications = async () => {
    try {
      const data = await notificationService.getAll(true); // unread only
      setNotifications(data);
      setUnreadCount(data.length);
    } catch (err) {
      console.error('Failed to fetch notifications', err);
    }
  };

  useEffect(() => {
    fetchNotifications();
    // Poll every 30 seconds
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleMarkAsRead = async (id) => {
    await notificationService.markAsRead(id);
    fetchNotifications();
  };

  const handleMarkAllAsRead = async () => {
    await notificationService.markAllAsRead();
    fetchNotifications();
  };

  const getNotificationColor = (type) => {
    switch(type) {
      case 'INCIDENT': return '#EF4444';
      case 'ABSENCE': return '#F59E0B';
      case 'HEALTH': return '#10B981';
      default: return 'var(--moonstone)';
    }
  };

  return (
    <div style={{ position: 'relative' }} ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          position: 'relative',
          padding: '8px',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}
      >
        {unreadCount > 0 ? (
          <>
            <BellRing size={22} color="var(--moonstone)" />
            <span style={{
              position: 'absolute',
              top: 0,
              right: 0,
              backgroundColor: '#EF4444',
              color: 'white',
              borderRadius: '50%',
              width: '18px',
              height: '18px',
              fontSize: '11px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          </>
        ) : (
          <Bell size={22} color="var(--text-light)" />
        )}
      </button>

      {isOpen && (
        <div style={{
          position: 'absolute',
          top: '45px',
          right: 0,
          width: '380px',
          maxHeight: '500px',
          backgroundColor: 'white',
          borderRadius: '12px',
          boxShadow: '0 10px 40px rgba(0,0,0,0.15)',
          zIndex: 1000,
          overflow: 'hidden'
        }}>
          <div style={{
            padding: '1rem',
            borderBottom: '1px solid var(--timberwolf)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <h4 style={{ margin: 0, color: 'var(--midnight-green)' }}>Notifications</h4>
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllAsRead}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--moonstone)',
                  cursor: 'pointer',
                  fontSize: '0.8rem'
                }}
              >
                Tout marquer lu
              </button>
            )}
          </div>
          <div style={{ maxHeight: '420px', overflowY: 'auto' }}>
            {notifications.length === 0 ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-light)' }}>
                Aucune notification
              </div>
            ) : (
              notifications.map(notif => (
                <div
                  key={notif.id}
                  style={{
                    padding: '1rem',
                    borderBottom: '1px solid var(--timberwolf)',
                    borderLeft: `3px solid ${getNotificationColor(notif.notification_type)}`,
                    backgroundColor: notif.is_read ? 'white' : '#F8FAFE'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <p style={{ margin: 0, fontSize: '0.85rem', flex: 1 }}>{notif.message}</p>
                    {!notif.is_read && (
                      <button
                        onClick={() => handleMarkAsRead(notif.id)}
                        style={{
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          marginLeft: '0.5rem'
                        }}
                      >
                        <X size={14} color="var(--text-light)" />
                      </button>
                    )}
                  </div>
                  <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.7rem', color: 'var(--text-light)' }}>
                    {new Date(notif.created_at).toLocaleString()}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}