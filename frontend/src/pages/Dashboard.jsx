import { useState, useEffect } from 'react';
import { Navigate, useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { LogOut, Activity, AlertCircle, ShieldAlert, Users, HeartPulse, UtensilsCrossed, Plus, Edit2, Trash2, X } from 'lucide-react';
import { mealService, notificationService } from '../services/mealService';  // ← AJOUTE CETTE LIGNE

const API_BASE = 'http://127.0.0.1:8000/api';

// -----------------------------------------------------------------------------
// COMPOSANT NOTIFICATION BELL (à intégrer dans le header)
// -----------------------------------------------------------------------------
function NotificationBell({ token }) {
  const [notifications, setNotifications] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  const fetchNotifications = async () => {
    try {
      const data = await notificationService.getAll(true);
      setNotifications(data);
      setUnreadCount(data.length);
    } catch (err) {
      console.error('Failed to fetch notifications', err);
    }
  };

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
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
    <>
      {/* Bouton cloche */}
      <button
        onClick={() => setIsOpen(true)}
        style={{ background: 'none', border: 'none', cursor: 'pointer', position: 'relative', padding: '8px' }}
      >
        {unreadCount > 0 ? (
          <>
            <span style={{ fontSize: '1.2rem' }}>🔔</span>
            <span style={{ position: 'absolute', top: 0, right: 0, backgroundColor: '#EF4444', color: 'white', borderRadius: '50%', width: '18px', height: '18px', fontSize: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          </>
        ) : (
          <span style={{ fontSize: '1.2rem', opacity: 0.5 }}>🔔</span>
        )}
      </button>

      {/* Modal comme pour Add Meal */}
      {isOpen && (
        <div style={{ 
          position: 'fixed', 
          top: 0, 
          left: 0, 
          right: 0, 
          bottom: 0, 
          backgroundColor: 'rgba(0,0,0,0.5)', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center', 
          zIndex: 1000 
        }}>
          <div style={{ 
            backgroundColor: 'white', 
            borderRadius: '12px', 
            width: '500px', 
            maxWidth: '90%', 
            maxHeight: '80%', 
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column'
          }}>
            {/* Header */}
            <div style={{ 
              padding: '1rem', 
              borderBottom: '1px solid #ddd', 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center',
              backgroundColor: 'var(--midnight-green)',
              color: 'white'
            }}>
              <h3 style={{ margin: 0 }}>🔔 Notifications</h3>
              <div>
                {unreadCount > 0 && (
                  <button 
                    onClick={handleMarkAllAsRead} 
                    style={{ 
                      background: 'rgba(255,255,255,0.2)', 
                      border: 'none', 
                      color: 'white', 
                      cursor: 'pointer', 
                      padding: '5px 10px', 
                      borderRadius: '5px',
                      marginRight: '10px'
                    }}
                  >
                    Tout lire
                  </button>
                )}
                <button 
                  onClick={() => setIsOpen(false)} 
                  style={{ 
                    background: 'rgba(255,255,255,0.2)', 
                    border: 'none', 
                    color: 'white', 
                    cursor: 'pointer', 
                    padding: '5px 10px', 
                    borderRadius: '5px' 
                  }}
                >
                  ✕
                </button>
              </div>
            </div>

            {/* Liste des notifications */}
            <div style={{ maxHeight: '500px', overflowY: 'auto', padding: '1rem' }}>
              {notifications.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '2rem', color: 'gray' }}>
                  ✅ Aucune notification non lue
                </div>
              ) : (
                notifications.map(notif => (
                  <div key={notif.id} style={{ 
                    padding: '1rem', 
                    marginBottom: '0.5rem',
                    borderRadius: '8px',
                    borderLeft: `4px solid ${getNotificationColor(notif.notification_type)}`,
                    backgroundColor: notif.is_read ? 'white' : '#F0F9FF',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div style={{ flex: 1 }}>
                        <strong style={{ color: getNotificationColor(notif.notification_type) }}>
                          {notif.notification_type === 'ABSENCE' ? '⚠️ ABSENCE' : notif.notification_type}
                        </strong>
                        <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.9rem' }}>{notif.message}</p>
                        <small style={{ color: 'gray', display: 'block', marginTop: '0.5rem' }}>
                          {new Date(notif.created_at).toLocaleString()}
                        </small>
                      </div>
                      {!notif.is_read && (
                        <button 
                          onClick={() => handleMarkAsRead(notif.id)} 
                          style={{ 
                            background: 'none', 
                            border: 'none', 
                            cursor: 'pointer', 
                            color: 'gray',
                            fontSize: '12px'
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
        </div>
      )}
    </>
  );
}

// -----------------------------------------------------------------------------
// CAREGIVER / STAFF DASHBOARD (MODIFIÉ)
// -----------------------------------------------------------------------------
function StaffDashboard({ token, onLogout }) {
  const [residents, setResidents] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('residents');
  const [meals, setMeals] = useState([]);
  const [showMealModal, setShowMealModal] = useState(false);
  const [editingMeal, setEditingMeal] = useState(null);
  const [mealForm, setMealForm] = useState({ name: '', time: '', expected_people: 4, zone: null });
  const [userRole, setUserRole] = useState('');
  const [incidents, setIncidents] = useState([]);
  // Décoder le rôle depuis le token
  useEffect(() => {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(window.atob(base64).split('').map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)).join(''));
      const decoded = JSON.parse(jsonPayload);
      setUserRole(decoded.role || '');
    } catch (err) {
      console.error('Error decoding token', err);
    }
  }, [token]);

  const fetchStaffDashboard = async () => {
    try {
      const response = await axios.get(`${API_BASE}/mobile/dashboard/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setResidents(response.data);
    } catch (err) {
      if (err.response?.status === 401) {
        onLogout();
      } else if (err.response?.status === 404) {
        setErrorMsg('No residents assigned to your shift yet.');
      } else if (err.response?.status === 403) {
        setErrorMsg('Access forbidden. You might not have the correct role permissions.');
      } else {
        setErrorMsg('An error occurred while fetching your dashboard.');
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchMeals = async () => {
    try {
      const data = await mealService.getAll();
      setMeals(data);
    } catch (err) {
      console.error('Failed to fetch meals', err);
    }
  };

  useEffect(() => {
    fetchStaffDashboard();
  }, [token, onLogout]);

  const handleSaveMeal = async (e) => {
    e.preventDefault();
    try {
      if (editingMeal) {
        await mealService.update(editingMeal.id, mealForm);
      } else {
        await mealService.create(mealForm);
      }
      setShowMealModal(false);
      fetchMeals();
    } catch (err) {
      console.error('Failed to save meal', err);
    }
  };

  const handleDeleteMeal = async (id) => {
    if (window.confirm('Delete this meal?')) {
      await mealService.delete(id);
      fetchMeals();
    }
  };
  const fetchIncidents = async () => {
  try {
    const response = await axios.get(`${API_BASE}/incidents/`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    setIncidents(response.data);
  } catch (err) {
    console.error('Failed to fetch incidents', err);
  }
  };
  if (loading) return <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--midnight-green)' }}><h2>Loading Staff Dashboard...</h2></div>;

  const isAdmin = userRole === 'ADMIN';

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: 'var(--alice-blue)' }}>
      {/* Sidebar */}
      <aside style={{ width: '260px', backgroundColor: 'var(--midnight-green)', color: 'white', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '1.5rem 2rem', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
          <Link to="/"><img src="/LOGO_AURACARE.png" alt="AuraCare Logo" style={{ height: '40px' }} /></Link>
        </div>

        <nav style={{ flex: 1, padding: '1rem' }}>
          <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', listStyle: 'none', padding: 0 }}>
            <li>
              <button
                onClick={() => setActiveTab('residents')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '10px 15px',
                  width: '100%',
                  backgroundColor: activeTab === 'residents' ? 'rgba(255,255,255,0.1)' : 'transparent',
                  borderRadius: 'var(--border-radius-sm)',
                  color: activeTab === 'residents' ? 'var(--moonstone)' : 'rgba(255,255,255,0.7)',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '1rem'
                }}
              >
                <Users size={18} /> Assigned Residents
              </button>
            </li>
            
            {isAdmin && (
              <>
                <li>
                  <button
                    onClick={() => { setActiveTab('meals'); fetchMeals(); }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      padding: '10px 15px',
                      width: '100%',
                      backgroundColor: activeTab === 'meals' ? 'rgba(255,255,255,0.1)' : 'transparent',
                      borderRadius: 'var(--border-radius-sm)',
                      color: activeTab === 'meals' ? 'var(--moonstone)' : 'rgba(255,255,255,0.7)',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '1rem'
                    }}
                  >
                    <UtensilsCrossed size={18} /> Meal Management
                  </button>
                </li>
                
                <li>
                  <button
                    onClick={() => { setActiveTab('incidents'); fetchIncidents(); }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      padding: '10px 15px',
                      width: '100%',
                      backgroundColor: activeTab === 'incidents' ? 'rgba(255,255,255,0.1)' : 'transparent',
                      borderRadius: 'var(--border-radius-sm)',
                      color: activeTab === 'incidents' ? 'var(--moonstone)' : 'rgba(255,255,255,0.7)',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '1rem'
                    }}
                  >
                    <ShieldAlert size={18} /> Incidents
                  </button>
                </li>
              </>
            )}
            
            <li>
              <Link to="/video-feed" style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '10px 15px',
                color: 'rgba(255,255,255,0.7)',
                textDecoration: 'none'
              }}>
                <Activity size={18} /> Live Camera
              </Link>
            </li>
          </ul>
        </nav>
        <div style={{ padding: '2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <NotificationBell token={token} />
          <button onClick={onLogout} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'rgba(255,255,255,0.7)', background: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem' }}>
            <LogOut size={18} /> Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main style={{ flex: 1, padding: '3rem' }}>
        {errorMsg ? (
          <div style={{ backgroundColor: 'white', padding: '3rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)', textAlign: 'center' }}>
            <AlertCircle size={48} color="var(--cadet-gray)" style={{ marginBottom: '1rem' }} />
            <h2 style={{ color: 'var(--midnight-green)', marginBottom: '1rem' }}>Dashboard Unavailable</h2>
            <p style={{ color: 'var(--text-light)', fontSize: '1.1rem' }}>{errorMsg}</p>
          </div>
        ) : (
          <>
            {activeTab === 'residents' && (
              <>
                <header style={{ marginBottom: '3rem' }}>
                  <h1 style={{ color: 'var(--midnight-green)', margin: 0 }}>Caregiver Dashboard</h1>
                  <p style={{ color: 'var(--text-light)', margin: 0 }}>Monitor all assigned residents for your shift</p>
                </header>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '2rem' }}>
                  {residents && residents.map(resident => (
                    <div key={resident.id} style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)', borderTop: `4px solid ${resident.risk_level === 'HIGH' ? '#EF4444' : resident.risk_level === 'MEDIUM' ? '#F59E0B' : 'var(--moonstone)'}` }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                        <div>
                          <h3 style={{ margin: 0, color: 'var(--midnight-green)' }}>{resident.name}</h3>
                          <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.9rem' }}>Room: {resident.room_number} | Age: {resident.age}</p>
                        </div>
                        <span style={{ fontSize: '0.8rem', fontWeight: 'bold', padding: '4px 8px', borderRadius: '12px', backgroundColor: resident.risk_level === 'HIGH' ? '#FEE2E2' : resident.risk_level === 'MEDIUM' ? '#FEF3C7' : '#E0F2FE', color: resident.risk_level === 'HIGH' ? '#B91C1C' : resident.risk_level === 'MEDIUM' ? '#B45309' : '#0369A1' }}>
                          {resident.risk_level} RISK
                        </span>
                      </div>
                      
                      <div style={{ padding: '1rem', backgroundColor: 'var(--alice-blue)', borderRadius: 'var(--border-radius-sm)', marginBottom: '1rem' }}>
                        <p style={{ margin: 0, fontWeight: 'bold', color: 'var(--midnight-green)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <HeartPulse size={16} color="var(--moonstone)" /> Recent Metrics
                        </p>
                        <ul style={{ listStyle: 'none', padding: 0, margin: '0.5rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-dark)' }}>
                          {resident.metrics && resident.metrics.length > 0 ? resident.metrics.slice(0, 3).map((m, idx) => (
                            <li key={idx} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                              <span>{m.metric_type_display}</span>
                              <span style={{ fontWeight: 'bold' }}>{m.value}</span>
                            </li>
                          )) : <li>No recent metrics.</li>}
                        </ul>
                      </div>

                      <div>
                        <p style={{ margin: 0, fontWeight: 'bold', color: '#EF4444', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <AlertCircle size={16} /> Recent Incidents
                        </p>
                        <ul style={{ listStyle: 'none', padding: 0, margin: '0.5rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-dark)' }}>
                          {resident.incidents && resident.incidents.length > 0 ? resident.incidents.slice(0, 2).map((inc, idx) => (
                            <li key={idx} style={{ padding: '0.5rem', backgroundColor: '#FEE2E2', borderRadius: '4px', marginBottom: '0.3rem' }}>
                              <strong>{inc.type_display}</strong> in {inc.zone?.name || 'Unknown'}
                            </li>
                          )) : <li style={{ color: 'var(--text-light)' }}>No recent incidents.</li>}
                        </ul>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}

            {activeTab === 'meals' && isAdmin && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
                  <div>
                    <h1 style={{ color: 'var(--midnight-green)', margin: 0 }}>Meal Management</h1>
                    <p style={{ color: 'var(--text-light)', margin: 0 }}>Configure daily meal schedules and expected attendance</p>
                  </div>
                  <button
                    onClick={() => { setEditingMeal(null); setMealForm({ name: '', time: '', expected_people: 4, zone: null }); setShowMealModal(true); }}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 20px', backgroundColor: 'var(--moonstone)', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer' }}
                  >
                    <Plus size={18} /> Add Meal
                  </button>
                </div>

                <div style={{ display: 'grid', gap: '1rem' }}>
                  {meals.map(meal => (
                    <div key={meal.id} style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <h3 style={{ margin: 0, color: 'var(--midnight-green)' }}>{meal.name}</h3>
                        <p style={{ margin: '0.5rem 0 0 0', color: 'var(--text-light)' }}>
                          {meal.time} | Expected: {meal.expected_people} people | Zone: {meal.zone_name || 'Not specified'}
                        </p>
                      </div>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button onClick={() => { setEditingMeal(meal); setMealForm(meal); setShowMealModal(true); }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--moonstone)' }}><Edit2 size={18} /></button>
                        <button onClick={() => handleDeleteMeal(meal.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#EF4444' }}><Trash2 size={18} /></button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </main>

      {/* Modal pour ajouter/modifier un repas */}
      {showMealModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ backgroundColor: 'white', borderRadius: '12px', padding: '2rem', width: '450px', maxWidth: '90%' }}>
            <h3 style={{ marginBottom: '1.5rem' }}>{editingMeal ? 'Edit Meal' : 'Add New Meal'}</h3>
            <form onSubmit={handleSaveMeal}>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', marginBottom: '0.5rem' }}>Meal Name</label>
                <input type="text" value={mealForm.name} onChange={e => setMealForm({...mealForm, name: e.target.value})} required style={{ width: '100%', padding: '8px', border: '1px solid #ddd', borderRadius: '4px' }} />
              </div>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', marginBottom: '0.5rem' }}>Time</label>
                <input type="time" value={mealForm.time} onChange={e => setMealForm({...mealForm, time: e.target.value})} required style={{ width: '100%', padding: '8px', border: '1px solid #ddd', borderRadius: '4px' }} />
              </div>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', marginBottom: '0.5rem' }}>Expected People</label>
                <input type="number" value={mealForm.expected_people} onChange={e => setMealForm({...mealForm, expected_people: parseInt(e.target.value)})} min="1" required style={{ width: '100%', padding: '8px', border: '1px solid #ddd', borderRadius: '4px' }} />
              </div>
              <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem' }}>
                <button type="submit" style={{ padding: '10px 20px', backgroundColor: 'var(--moonstone)', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>{editingMeal ? 'Update' : 'Create'}</button>
                <button type="button" onClick={() => setShowMealModal(false)} style={{ padding: '10px 20px', backgroundColor: '#ccc', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------------
// FAMILY DASHBOARD (inchangé)
// -----------------------------------------------------------------------------
function FamilyDashboard({ token, onLogout }) {
  const [data, setData] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const response = await axios.get(`${API_BASE}/mobile/activity-log/`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setData(response.data);
      } catch (err) {
        if (err.response?.status === 401) {
          onLogout();
        } else if (err.response?.status === 404) {
          setErrorMsg('No residents assigned to your account yet.');
        } else if (err.response?.status === 403) {
          setErrorMsg('Access forbidden. You might not have the correct role permissions.');
        } else {
          setErrorMsg('An error occurred while fetching your dashboard.');
        }
      } finally {
        setLoading(false);
      }
    };
    fetchDashboard();
  }, [token, onLogout]);

  if (loading) return <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--midnight-green)' }}><h2>Loading AI Telemetry...</h2></div>;

  const tempChartData = data ? [
    { name: 'Mon', gait: 0.8, social: data.average_social_score_7d - 5 || 50 },
    { name: 'Tue', gait: 0.9, social: data.average_social_score_7d + 2 || 55 },
    { name: 'Wed', gait: 1.0, social: data.average_social_score_7d - 1 || 52 },
    { name: 'Thu', gait: 0.9, social: data.average_social_score_7d + 5 || 60 },
    { name: 'Fri', gait: 0.7, social: data.average_social_score_7d - 3 || 45 },
    { name: 'Sat', gait: 0.85, social: data.average_social_score_7d || 53 },
    { name: 'Sun', gait: 0.92, social: data.average_social_score_7d + 1 || 55 },
  ] : [];

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: 'var(--alice-blue)' }}>
      <aside style={{ width: '260px', backgroundColor: 'var(--midnight-green)', color: 'white', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '1.5rem 2rem', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
          <Link to="/"><img src="/LOGO_AURACARE.png" alt="AuraCare Logo" style={{ height: '40px' }} /></Link>
        </div>
        <nav style={{ flex: 1, padding: '1rem' }}>
          <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', listStyle: 'none', padding: 0 }}>
            <li><a href="#" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: 'var(--border-radius-sm)', color: 'var(--moonstone)', textDecoration: 'none' }}><Activity size={18} /> Overview</a></li>
            <li><a href="#" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', color: 'rgba(255,255,255,0.7)', textDecoration: 'none' }}><ShieldAlert size={18} /> Incident Logs</a></li>
          </ul>
        </nav>
        <div style={{ padding: '2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <NotificationBell token={token} />
          <button onClick={onLogout} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'rgba(255,255,255,0.7)', background: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem' }}><LogOut size={18} /> Sign Out</button>
        </div>
      </aside>

      <main style={{ flex: 1, padding: '3rem' }}>
        {errorMsg ? (
          <div style={{ backgroundColor: 'white', padding: '3rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)', textAlign: 'center' }}>
            <AlertCircle size={48} color="var(--cadet-gray)" style={{ marginBottom: '1rem' }} />
            <h2 style={{ color: 'var(--midnight-green)', marginBottom: '1rem' }}>Dashboard Unavailable</h2>
            <p style={{ color: 'var(--text-light)', fontSize: '1.1rem' }}>{errorMsg}</p>
          </div>
        ) : (
          <>
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3rem' }}>
              <div><h1 style={{ color: 'var(--midnight-green)', margin: 0 }}>Resident Overview</h1><p style={{ color: 'var(--text-light)', margin: 0 }}>Monitoring: {data?.resident_name}</p></div>
              <div style={{ padding: '10px 20px', backgroundColor: 'white', borderRadius: 'var(--border-radius-sm)', boxShadow: 'var(--box-shadow)' }}><span style={{ color: 'var(--text-light)', fontSize: '0.9rem' }}>Status: </span><span style={{ color: 'var(--moonstone)', fontWeight: 'bold' }}>Active & Secure</span></div>
            </header>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '2rem', marginBottom: '3rem' }}>
              <div style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)' }}>
                <h4 style={{ color: 'var(--text-light)', margin: 0 }}>Social Interaction Score</h4>
                <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: 'var(--midnight-green)' }}>{data?.average_social_score_7d ? data.average_social_score_7d.toFixed(1) : 'N/A'}</div>
                <p style={{ color: 'var(--moonstone)', fontSize: '0.9rem', margin: 0 }}>Last 7 Days Avg</p>
              </div>
              <div style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)' }}>
                <h4 style={{ color: 'var(--text-light)', margin: 0 }}>Recent Incidents</h4>
                <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: '#EF4444' }}>{data?.recent_incidents?.length || 0}</div>
                <p style={{ color: 'var(--text-light)', fontSize: '0.9rem', margin: 0 }}>Pending review</p>
              </div>
              <div style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)' }}>
                <h4 style={{ color: 'var(--text-light)', margin: 0 }}>Active Monitors</h4>
                <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: 'var(--moonstone)' }}>7</div>
                <p style={{ color: 'var(--text-light)', fontSize: '0.9rem', margin: 0 }}>All Zones Nominal</p>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '2rem' }}>
              <div style={{ backgroundColor: 'white', padding: '2rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)' }}>
                <h3 style={{ color: 'var(--midnight-green)', marginBottom: '1.5rem' }}>Weekly Telemetry Trends</h3>
                <div style={{ height: 300 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={tempChartData}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E9F1F6" />
                      <XAxis dataKey="name" axisLine={false} tickLine={false} />
                      <YAxis yAxisId="left" axisLine={false} tickLine={false} />
                      <YAxis yAxisId="right" orientation="right" axisLine={false} tickLine={false} />
                      <Tooltip />
                      <Legend />
                      <Line yAxisId="left" type="monotone" dataKey="social" stroke="var(--moonstone)" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 8 }} name="Social Score" />
                      <Line yAxisId="right" type="monotone" dataKey="gait" stroke="var(--midnight-green)" strokeWidth={3} dot={{ r: 4 }} name="Gait Speed (m/s)" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div style={{ backgroundColor: 'white', padding: '2rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)' }}>
                <h3 style={{ color: 'var(--midnight-green)', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}><AlertCircle color="#EF4444" /> Incident Feed</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {data?.recent_incidents && data.recent_incidents.length > 0 ? (
                    data.recent_incidents.map((incident, idx) => (
                      <div key={idx} style={{ padding: '1rem', borderLeft: '4px solid #EF4444', backgroundColor: 'var(--alice-blue)', borderRadius: '0 var(--border-radius-sm) var(--border-radius-sm) 0' }}>
                        <p style={{ margin: '0 0 0.5rem 0', fontWeight: 'bold', color: 'var(--midnight-green)' }}>{incident.type_display} detected</p>
                        <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-light)' }}>Zone: {incident.zone?.name || 'Unknown'}</p>
                        <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-light)' }}>{new Date(incident.timestamp).toLocaleString()}</p>
                      </div>
                    ))
                  ) : (
                    <p style={{ color: 'var(--text-light)', fontStyle: 'italic' }}>No recent incidents.</p>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

// -----------------------------------------------------------------------------
// MAIN DASHBOARD ROUTER WIDGET
// -----------------------------------------------------------------------------
export default function Dashboard() {
  const navigate = useNavigate();
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    return <Navigate to="/login" />;
  }

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    navigate('/login');
  };

  let role = 'FAMILY';
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(window.atob(base64).split('').map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)).join(''));
    const decoded = JSON.parse(jsonPayload);
    if (decoded && decoded.role) role = decoded.role;
  } catch (err) {
    console.error('Invalid token format', err);
  }

  if (role === 'CAREGIVER' || role === 'ADMIN') {
    return <StaffDashboard token={token} onLogout={handleLogout} />;
  }

  return <FamilyDashboard token={token} onLogout={handleLogout} />;
}