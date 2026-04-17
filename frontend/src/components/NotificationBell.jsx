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

export default function NotificationBell({ token }) {
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
      const data = await notificationService.getAll(token, false);
      const unread = data.filter((item) => !item.is_read);
      const newUnread = unread.filter((item) => !playedIdsRef.current.has(item.id));
      if (newUnread.length > 0 && isEnabled) {
        playSound();
        newUnread.forEach((item) => playedIdsRef.current.add(item.id));
        savePlayedIds(playedIdsRef.current);
      }
      setNotifications(data);
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

  return (
    <div ref={dropdownRef} style={{ position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem' }}>
        <div>
          <p style={{ margin: 0, color: 'rgba(255,255,255,0.65)', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Alerts</p>
          <p style={{ margin: '0.2rem 0 0', color: 'white', fontWeight: 700 }}>{unreadCount} unread</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <button
            type="button"
            onClick={toggleSound}
            style={{ border: 'none', borderRadius: '10px', backgroundColor: 'rgba(255,255,255,0.12)', color: 'white', width: '36px', height: '36px', display: 'grid', placeItems: 'center', cursor: 'pointer' }}
            title={isEnabled ? 'Mute alert sound' : 'Enable alert sound'}
          >
            {isEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
          </button>
          <button
            type="button"
            onClick={() => setIsOpen((current) => !current)}
            style={{ border: 'none', borderRadius: '10px', backgroundColor: unreadCount > 0 ? 'rgba(245,158,11,0.18)' : 'rgba(255,255,255,0.12)', color: unreadCount > 0 ? '#FCD34D' : 'white', width: '42px', height: '36px', display: 'grid', placeItems: 'center', cursor: 'pointer', position: 'relative' }}
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
        <div style={{ position: 'absolute', left: 'calc(100% + 12px)', bottom: 0, width: '380px', maxHeight: '470px', overflow: 'hidden', borderRadius: '20px', backgroundColor: 'white', boxShadow: '0 20px 60px rgba(15, 43, 68, 0.24)', zIndex: 20 }}>
          <div style={{ padding: '1rem 1.1rem', background: 'linear-gradient(135deg, var(--midnight-green) 0%, #123B57 100%)', color: 'white', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.75rem' }}>
            <div>
              <p style={{ margin: 0, fontSize: '0.8rem', opacity: 0.75 }}>Meriem module</p>
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
                <p style={{ margin: 0, fontWeight: 700, color: 'var(--midnight-green)' }}>No alerts yet</p>
                <p style={{ margin: '0.4rem 0 0' }}>Meal absences and related alerts will appear here.</p>
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
