import { useEffect, useRef, useState } from 'react';
import { Bell, BellRing, Volume2, VolumeX, CheckCheck } from 'lucide-react';
import { notificationService } from '../services/mealService';
import { useNotificationSound } from '../hooks/useNotificationSound';

const PLAYED_STORAGE_KEY = 'auracare.notifications.played';

const getPlayedIds = () => {
  if (typeof window === 'undefined') return new Set();
  try {
    const raw = window.localStorage.getItem(PLAYED_STORAGE_KEY);
    const parsed = JSON.parse(raw || '[]');
    return new Set(Array.isArray(parsed) ? parsed : []);
  } catch {
    return new Set();
  }
};

const savePlayedIds = (ids) => {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(PLAYED_STORAGE_KEY, JSON.stringify([...ids].slice(-100)));
};

export default function NotificationBell({ token, compact = false, dropdownAlign = 'side' }) {
  const [notifications, setNotifications] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState('');
  const dropdownRef = useRef(null);
  const playedIdsRef = useRef(getPlayedIds());
  const { playSound, toggleSound, isEnabled } = useNotificationSound();

  const unreadCount = notifications.filter((notification) => !notification.is_read).length;

  const fetchNotifications = async () => {
    try {
      setError('');
      const todayIncidents = await notificationService.getAll(token, {
        incidentOnly: true,
        todayOnly: true,
      });
      const unread = todayIncidents.filter((item) => !item.is_read);
      const newUnread = unread.filter((item) => !playedIdsRef.current.has(item.id));
      if (newUnread.length > 0 && isEnabled) {
        playSound();
        newUnread.forEach((item) => playedIdsRef.current.add(item.id));
        savePlayedIds(playedIdsRef.current);
      }
      setNotifications(todayIncidents);
    } catch (err) {
      setError(err.response?.status === 401 ? 'Session expired.' : 'Notifications unavailable.');
    }
  };

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      fetchNotifications();
    }, 0);
    const intervalId = window.setInterval(fetchNotifications, 10000);
    return () => {
      window.clearTimeout(timeoutId);
      window.clearInterval(intervalId);
    };
  }, [token, isEnabled]); // eslint-disable-line react-hooks/exhaustive-deps

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
    try {
      await notificationService.markAsRead(id, token);
      fetchNotifications();
    } catch (err) {
      setError(err.response?.status === 401 ? 'Session expired.' : 'Unable to mark this notification as read.');
    }
  };

  const handleMarkAllAsRead = async () => {
    try {
      await notificationService.markAllAsRead(token);
      fetchNotifications();
    } catch (err) {
      setError(err.response?.status === 401 ? 'Session expired.' : 'Unable to update notifications.');
    }
  };

  const notificationAccent = (type) => {
    switch (type) {
      case 'ABSENCE':
        return { bg: '#FFF7ED', border: '#F59E0B', text: '#9A3412', label: 'Meal Alert' };
      case 'INCIDENT':
        return { bg: '#FEF2F2', border: '#EF4444', text: '#991B1B', label: 'Incident' };
      case 'HEALTH':
        return { bg: '#ECFDF5', border: '#10B981', text: '#065F46', label: 'Health' };
      default:
        return { bg: '#F0F9FF', border: '#38BDF8', text: '#0C4A6E', label: 'Info' };
    }
  };

  const dropdownStyle = dropdownAlign === 'top-right'
    ? {
      position: 'absolute',
      top: 'calc(100% + 12px)',
      right: 0,
      width: '380px',
      maxHeight: '470px',
      overflow: 'hidden',
      borderRadius: '20px',
      backgroundColor: 'white',
      boxShadow: '0 20px 60px rgba(15, 43, 68, 0.24)',
      zIndex: 20,
    }
    : {
      position: 'absolute',
      left: 'calc(100% + 12px)',
      bottom: 0,
      width: '380px',
      maxHeight: '470px',
      overflow: 'hidden',
      borderRadius: '20px',
      backgroundColor: 'white',
      boxShadow: '0 20px 60px rgba(15, 43, 68, 0.24)',
      zIndex: 20,
    };

  return (
    <div ref={dropdownRef} style={{ position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: compact ? 'flex-end' : 'space-between', gap: '0.75rem' }}>
        {!compact && (
          <div>
            <p style={{ margin: 0, color: 'rgba(255,255,255,0.65)', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Alerts</p>
            <p style={{ margin: '0.2rem 0 0', color: 'white', fontWeight: 700 }}>{unreadCount} unread</p>
          </div>
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <button
            type="button"
            onClick={toggleSound}
            style={{
              border: compact ? '1px solid rgba(0,69,84,0.18)' : '1px solid rgba(255,255,255,0.2)',
              borderRadius: '10px',
              backgroundColor: compact ? '#E6F4FA' : 'rgba(255,255,255,0.12)',
              color: compact ? 'var(--midnight-green)' : 'white',
              width: '36px',
              height: '36px',
              display: 'grid',
              placeItems: 'center',
              cursor: 'pointer',
              transition: 'transform 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease',
              boxShadow: compact ? '0 2px 6px rgba(0,69,84,0.08)' : 'none',
            }}
            onMouseEnter={(event) => {
              event.currentTarget.style.transform = 'translateY(-1px) scale(1.02)';
              event.currentTarget.style.boxShadow = compact ? '0 8px 16px rgba(0,69,84,0.16)' : '0 8px 14px rgba(0,0,0,0.16)';
              event.currentTarget.style.borderColor = compact ? 'rgba(0,69,84,0.28)' : 'rgba(255,255,255,0.38)';
            }}
            onMouseLeave={(event) => {
              event.currentTarget.style.transform = 'translateY(0) scale(1)';
              event.currentTarget.style.boxShadow = compact ? '0 2px 6px rgba(0,69,84,0.08)' : 'none';
              event.currentTarget.style.borderColor = compact ? 'rgba(0,69,84,0.18)' : 'rgba(255,255,255,0.2)';
            }}
            onMouseDown={(event) => {
              event.currentTarget.style.transform = 'translateY(0) scale(0.98)';
            }}
            onMouseUp={(event) => {
              event.currentTarget.style.transform = 'translateY(-1px) scale(1.02)';
            }}
            title={isEnabled ? 'Mute alert sound' : 'Enable alert sound'}
          >
            {isEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
          </button>
          <button
            type="button"
            onClick={() => setIsOpen((current) => !current)}
            style={{
              border: compact
                ? `1px solid ${unreadCount > 0 ? 'rgba(245,158,11,0.35)' : 'rgba(0,69,84,0.18)'}`
                : `1px solid ${unreadCount > 0 ? 'rgba(252,211,77,0.45)' : 'rgba(255,255,255,0.22)'}`,
              borderRadius: '10px',
              backgroundColor: unreadCount > 0
                ? (compact ? '#FEF3C7' : 'rgba(245,158,11,0.18)')
                : (compact ? '#E6F4FA' : 'rgba(255,255,255,0.12)'),
              color: unreadCount > 0
                ? (compact ? '#B45309' : '#FCD34D')
                : (compact ? 'var(--midnight-green)' : 'white'),
              width: '42px',
              height: '36px',
              display: 'grid',
              placeItems: 'center',
              cursor: 'pointer',
              position: 'relative',
              transition: 'transform 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease',
              boxShadow: compact
                ? (unreadCount > 0 ? '0 3px 8px rgba(245,158,11,0.18)' : '0 2px 6px rgba(0,69,84,0.08)')
                : 'none',
            }}
            onMouseEnter={(event) => {
              event.currentTarget.style.transform = 'translateY(-1px) scale(1.02)';
              event.currentTarget.style.boxShadow = unreadCount > 0
                ? '0 10px 18px rgba(245,158,11,0.22)'
                : (compact ? '0 8px 16px rgba(0,69,84,0.16)' : '0 8px 14px rgba(0,0,0,0.16)');
              event.currentTarget.style.borderColor = unreadCount > 0
                ? (compact ? 'rgba(245,158,11,0.55)' : 'rgba(252,211,77,0.7)')
                : (compact ? 'rgba(0,69,84,0.28)' : 'rgba(255,255,255,0.4)');
            }}
            onMouseLeave={(event) => {
              event.currentTarget.style.transform = 'translateY(0) scale(1)';
              event.currentTarget.style.boxShadow = compact
                ? (unreadCount > 0 ? '0 3px 8px rgba(245,158,11,0.18)' : '0 2px 6px rgba(0,69,84,0.08)')
                : 'none';
              event.currentTarget.style.borderColor = compact
                ? (unreadCount > 0 ? 'rgba(245,158,11,0.35)' : 'rgba(0,69,84,0.18)')
                : (unreadCount > 0 ? 'rgba(252,211,77,0.45)' : 'rgba(255,255,255,0.22)');
            }}
            onMouseDown={(event) => {
              event.currentTarget.style.transform = 'translateY(0) scale(0.98)';
            }}
            onMouseUp={(event) => {
              event.currentTarget.style.transform = 'translateY(-1px) scale(1.02)';
            }}
          >
            {unreadCount > 0 ? <BellRing size={18} /> : <Bell size={18} />}
            {unreadCount > 0 && (
              <span style={{ position: 'absolute', top: '-6px', right: '-5px', minWidth: '20px', height: '20px', borderRadius: '999px', backgroundColor: '#EF4444', color: 'white', fontSize: '0.7rem', fontWeight: 700, display: 'grid', placeItems: 'center', padding: '0 5px' }}>
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>
        </div>
      </div>

      {isOpen && (
        <div style={dropdownStyle}>
          <div style={{ padding: '1rem 1.1rem', background: 'linear-gradient(135deg, var(--midnight-green) 0%, #123B57 100%)', color: 'white', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.75rem' }}>
            <div>
              <h3 style={{ margin: '0.2rem 0 0', fontSize: '1rem' }}>Notifications</h3>
            </div>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={handleMarkAllAsRead}
                style={{ border: 'none', borderRadius: '999px', padding: '8px 12px', backgroundColor: 'rgba(255,255,255,0.15)', color: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.35rem', fontWeight: 700 }}
              >
                <CheckCheck size={14} /> Mark all
              </button>
            )}
          </div>

          <div style={{ maxHeight: '390px', overflowY: 'auto', padding: '0.75rem' }}>
            {error ? (
              <p style={{ margin: 0, color: '#B91C1C', padding: '1rem' }}>{error}</p>
            ) : notifications.length === 0 ? (
              <div style={{ padding: '2.5rem 1rem', textAlign: 'center', color: 'var(--text-light)' }}>
                <Bell size={28} style={{ opacity: 0.45, marginBottom: '0.75rem' }} />
                <p style={{ margin: 0, fontWeight: 700, color: 'var(--midnight-green)' }}>no incidents happened today</p>
              </div>
            ) : (
              notifications.map((notification) => {
                const accent = notificationAccent(notification.notification_type);
                return (
                  <article
                    key={notification.id}
                    onClick={() => handleMarkAsRead(notification.id)}
                    style={{ padding: '0.95rem 1rem', borderRadius: '16px', marginBottom: '0.7rem', backgroundColor: accent.bg, borderLeft: `4px solid ${accent.border}`, cursor: 'pointer', opacity: notification.is_read ? 0.78 : 1 }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem' }}>
                      <div>
                        <p style={{ margin: 0, color: accent.text, fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          {accent.label}
                        </p>
                        <p style={{ margin: '0.35rem 0 0', color: 'var(--text-dark)', lineHeight: 1.45 }}>
                          {notification.message}
                        </p>
                        <p style={{ margin: '0.45rem 0 0', color: 'var(--text-light)', fontSize: '0.76rem' }}>
                          {new Date(notification.created_at).toLocaleString()}
                        </p>
                      </div>
                      {!notification.is_read && (
                        <span style={{ alignSelf: 'start', padding: '4px 8px', borderRadius: '999px', backgroundColor: 'white', color: accent.text, fontSize: '0.7rem', fontWeight: 800 }}>
                          New
                        </span>
                      )}
                    </div>
                  </article>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
