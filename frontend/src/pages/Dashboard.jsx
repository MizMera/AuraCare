import { useState, useEffect } from 'react';
import { Navigate, useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { LogOut, Activity, AlertCircle, ShieldAlert, Users, HeartPulse, UtensilsCrossed, Plus, Edit2, Trash2, X, CheckCheck, Bell, BellRing } from 'lucide-react';
import { mealService, notificationService } from '../services/mealService';
import NotificationBell from '../components/NotificationBell';
const API_BASE = 'http://127.0.0.1:8000/api';



// -----------------------------------------------------------------------------
// CAREGIVER / STAFF DASHBOARD AMÉLIORÉ
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
  const [unreadCount, setUnreadCount] = useState(0);

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

  const handleMarkAllIncidentsRead = async () => {
    await notificationService.markAllAsRead();
    fetchIncidents();
  };

  if (loading) return <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--midnight-green)' }}><h2>Loading Staff Dashboard...</h2></div>;

  const isAdmin = userRole === 'ADMIN';

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: '#F3F4F6' }}>
      {/* Sidebar */}
      <aside style={{ 
        width: '280px', 
        backgroundColor: '#1E3A5F', 
        color: 'white', 
        display: 'flex', 
        flexDirection: 'column',
        boxShadow: '4px 0 20px rgba(0,0,0,0.1)'
      }}>
        <div style={{ padding: '1.5rem 2rem', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
          <Link to="/">
            <img src="/LOGO_AURACARE.png" alt="AuraCare Logo" style={{ height: '45px' }} />
          </Link>
        </div>
        
        <nav style={{ flex: 1, padding: '1.5rem 1rem' }}>
          <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', listStyle: 'none', padding: 0 }}>
            <li>
              <button
                onClick={() => setActiveTab('residents')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.75rem',
                  padding: '12px 16px',
                  width: '100%',
                  backgroundColor: activeTab === 'residents' ? 'rgba(255,255,255,0.15)' : 'transparent',
                  borderRadius: '12px',
                  color: activeTab === 'residents' ? 'white' : 'rgba(255,255,255,0.7)',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '0.9rem',
                  fontWeight: activeTab === 'residents' ? '600' : '400',
                  transition: 'all 0.2s'
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
                      gap: '0.75rem',
                      padding: '12px 16px',
                      width: '100%',
                      backgroundColor: activeTab === 'meals' ? 'rgba(255,255,255,0.15)' : 'transparent',
                      borderRadius: '12px',
                      color: activeTab === 'meals' ? 'white' : 'rgba(255,255,255,0.7)',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '0.9rem',
                      transition: 'all 0.2s'
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
                      justifyContent: 'space-between',
                      padding: '12px 16px',
                      width: '100%',
                      backgroundColor: activeTab === 'incidents' ? 'rgba(255,255,255,0.15)' : 'transparent',
                      borderRadius: '12px',
                      color: activeTab === 'incidents' ? 'white' : 'rgba(255,255,255,0.7)',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '0.9rem',
                      transition: 'all 0.2s'
                    }}
                  >
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <ShieldAlert size={18} /> Incidents
                    </span>
                    {unreadCount > 0 && (
                      <span style={{
                        backgroundColor: '#EF4444',
                        color: 'white',
                        fontSize: '0.7rem',
                        padding: '2px 8px',
                        borderRadius: '20px'
                      }}>
                        {unreadCount}
                      </span>
                    )}
                  </button>
                </li>
              </>
            )}
            
            <li>
              <Link to="/video-feed" style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '12px 16px',
                color: 'rgba(255,255,255,0.7)',
                textDecoration: 'none',
                fontSize: '0.9rem',
                borderRadius: '12px',
                transition: 'all 0.2s'
              }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.1)'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}>
                <Activity size={18} /> Live Camera
              </Link>
            </li>
          </ul>
        </nav>
        
        <div style={{ padding: '1.5rem', borderTop: '1px solid rgba(255,255,255,0.1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <NotificationBell token={token} onUnreadCountChange={setUnreadCount} />
          <button 
            onClick={onLogout} 
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '0.5rem', 
              color: 'rgba(255,255,255,0.7)', 
              background: 'none', 
              border: 'none', 
              cursor: 'pointer', 
              fontSize: '0.9rem',
              padding: '8px 12px',
              borderRadius: '8px',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.1)';
              e.currentTarget.style.color = 'white';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent';
              e.currentTarget.style.color = 'rgba(255,255,255,0.7)';
            }}
          >
            <LogOut size={18} /> Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main style={{ flex: 1, padding: '2rem', overflowY: 'auto' }}>
        {errorMsg ? (
          <div style={{ backgroundColor: 'white', padding: '3rem', borderRadius: '16px', boxShadow: '0 4px 20px rgba(0,0,0,0.08)', textAlign: 'center' }}>
            <AlertCircle size={48} color="#9CA3AF" style={{ marginBottom: '1rem' }} />
            <h2 style={{ color: '#1E3A5F', marginBottom: '1rem' }}>Dashboard Unavailable</h2>
            <p style={{ color: '#6B7280', fontSize: '1.1rem' }}>{errorMsg}</p>
          </div>
        ) : (
          <>
            {activeTab === 'residents' && (
              <>
                <header style={{ marginBottom: '2rem' }}>
                  <h1 style={{ color: '#1E3A5F', margin: 0, fontSize: '1.8rem' }}>Caregiver Dashboard</h1>
                  <p style={{ color: '#6B7280', margin: '0.5rem 0 0 0' }}>Monitor all assigned residents for your shift</p>
                </header>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '1.5rem' }}>
                  {residents && residents.map(resident => (
                    <div key={resident.id} style={{ 
                      backgroundColor: 'white', 
                      padding: '1.5rem', 
                      borderRadius: '16px', 
                      boxShadow: '0 4px 20px rgba(0,0,0,0.08)', 
                      borderTop: `4px solid ${resident.risk_level === 'HIGH' ? '#EF4444' : resident.risk_level === 'MEDIUM' ? '#F59E0B' : '#10B981'}`,
                      transition: 'transform 0.2s'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-4px)'}
                    onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                        <div>
                          <h3 style={{ margin: 0, color: '#1E3A5F' }}>{resident.name}</h3>
                          <p style={{ margin: 0, color: '#6B7280', fontSize: '0.85rem' }}>Room: {resident.room_number} | Age: {resident.age}</p>
                        </div>
                        <span style={{ 
                          fontSize: '0.7rem', 
                          fontWeight: 'bold', 
                          padding: '4px 10px', 
                          borderRadius: '20px', 
                          backgroundColor: resident.risk_level === 'HIGH' ? '#FEE2E2' : resident.risk_level === 'MEDIUM' ? '#FEF3C7' : '#D1FAE5', 
                          color: resident.risk_level === 'HIGH' ? '#B91C1C' : resident.risk_level === 'MEDIUM' ? '#B45309' : '#065F46' 
                        }}>
                          {resident.risk_level} RISK
                        </span>
                      </div>
                      
                      <div style={{ padding: '1rem', backgroundColor: '#F9FAFB', borderRadius: '12px', marginBottom: '1rem' }}>
                        <p style={{ margin: 0, fontWeight: 'bold', color: '#1E3A5F', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <HeartPulse size={16} color="#10B981" /> Recent Metrics
                        </p>
                        <ul style={{ listStyle: 'none', padding: 0, margin: '0.5rem 0 0 0', fontSize: '0.85rem', color: '#374151' }}>
                          {resident.metrics && resident.metrics.length > 0 ? resident.metrics.slice(0, 3).map((m, idx) => (
                            <li key={idx} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                              <span>{m.metric_type_display}</span>
                              <span style={{ fontWeight: 'bold' }}>{m.value}</span>
                            </li>
                          )) : <li>Aucune métrique récente</li>}
                        </ul>
                      </div>

                      <div>
                        <p style={{ margin: 0, fontWeight: 'bold', color: '#EF4444', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <AlertCircle size={16} /> Incidents récents
                        </p>
                        <ul style={{ listStyle: 'none', padding: 0, margin: '0.5rem 0 0 0', fontSize: '0.85rem', color: '#374151' }}>
                          {resident.incidents && resident.incidents.length > 0 ? resident.incidents.slice(0, 2).map((inc, idx) => (
                            <li key={idx} style={{ padding: '0.5rem', backgroundColor: '#FEE2E2', borderRadius: '8px', marginBottom: '0.3rem' }}>
                              <strong>{inc.type_display}</strong> in {inc.zone?.name || 'Unknown'}
                            </li>
                          )) : <li style={{ color: '#6B7280' }}>Aucun incident récent</li>}
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
                    <h1 style={{ color: '#1E3A5F', margin: 0, fontSize: '1.8rem' }}>Meal Management</h1>
                    <p style={{ color: '#6B7280', margin: '0.5rem 0 0 0' }}>Configure daily meal schedules and expected attendance</p>
                  </div>
                  <button
                    onClick={() => { setEditingMeal(null); setMealForm({ name: '', time: '', expected_people: 4, zone: null }); setShowMealModal(true); }}
                    style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: '0.5rem', 
                      padding: '10px 20px', 
                      backgroundColor: '#1E3A5F', 
                      color: 'white', 
                      border: 'none', 
                      borderRadius: '12px', 
                      cursor: 'pointer',
                      fontWeight: '600',
                      transition: 'all 0.2s'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#0F2B44'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#1E3A5F'}
                  >
                    <Plus size={18} /> Add Meal
                  </button>
                </div>

                <div style={{ display: 'grid', gap: '1rem' }}>
                  {meals.map(meal => (
                    <div key={meal.id} style={{ 
                      backgroundColor: 'white', 
                      padding: '1.5rem', 
                      borderRadius: '16px', 
                      boxShadow: '0 4px 20px rgba(0,0,0,0.08)', 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center',
                      transition: 'transform 0.2s'
                    }}>
                      <div>
                        <h3 style={{ margin: 0, color: '#1E3A5F' }}>{meal.name}</h3>
                        <p style={{ margin: '0.5rem 0 0 0', color: '#6B7280' }}>
                          {meal.time} | Attendus: {meal.expected_people} personnes | Zone: {meal.zone_name || 'Non spécifiée'}
                        </p>
                      </div>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button 
                          onClick={() => { setEditingMeal(meal); setMealForm(meal); setShowMealModal(true); }} 
                          style={{ 
                            background: 'none', 
                            border: 'none', 
                            cursor: 'pointer', 
                            color: '#1E3A5F',
                            padding: '8px',
                            borderRadius: '8px',
                            transition: 'all 0.2s'
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#F3F4F6'}
                          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                        >
                          <Edit2 size={18} />
                        </button>
                        <button 
                          onClick={() => handleDeleteMeal(meal.id)} 
                          style={{ 
                            background: 'none', 
                            border: 'none', 
                            cursor: 'pointer', 
                            color: '#EF4444',
                            padding: '8px',
                            borderRadius: '8px',
                            transition: 'all 0.2s'
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#FEE2E2'}
                          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                        >
                          <Trash2 size={18} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === 'incidents' && isAdmin && (
              <div>
                <header style={{ marginBottom: '2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <h1 style={{ color: '#1E3A5F', margin: 0, fontSize: '1.8rem' }}>Incidents Log</h1>
                    <p style={{ color: '#6B7280', margin: '0.5rem 0 0 0' }}>Historique des incidents et alertes</p>
                  </div>
                  {unreadCount > 0 && (
                    <button
                      onClick={handleMarkAllIncidentsRead}
                      style={{
                        padding: '8px 16px',
                        backgroundColor: '#F59E0B',
                        color: 'white',
                        border: 'none',
                        borderRadius: '12px',
                        cursor: 'pointer',
                        fontSize: '0.85rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        fontWeight: '500',
                        transition: 'all 0.2s'
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#D97706'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#F59E0B'}
                    >
                      <CheckCheck size={16} /> Tout marquer lu ({unreadCount})
                    </button>
                  )}
                </header>

                <div style={{ display: 'grid', gap: '1rem' }}>
                  {incidents.length > 0 ? (
                    incidents.map(incident => (
                      <div key={incident.id} style={{ 
                        backgroundColor: 'white', 
                        padding: '1.5rem', 
                        borderRadius: '16px', 
                        boxShadow: '0 4px 20px rgba(0,0,0,0.08)',
                        borderLeft: `4px solid ${incident.severity === 'CRITICAL' ? '#EF4444' : incident.severity === 'HIGH' ? '#F59E0B' : '#10B981'}`,
                        transition: 'transform 0.2s'
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                          <div>
                            <h3 style={{ margin: 0, color: '#1E3A5F' }}>
                              {incident.type_display || incident.type}
                            </h3>
                            <p style={{ margin: '0.5rem 0 0 0', color: '#6B7280', fontSize: '0.85rem' }}>
                              Zone: {incident.zone?.name || 'Inconnue'} | Sévérité: {incident.severity}
                            </p>
                            {incident.meal && (
                              <p style={{ margin: '0.5rem 0 0 0', color: '#F59E0B', fontSize: '0.85rem' }}>
                                Repas: {incident.meal.name} à {incident.meal.time}
                              </p>
                            )}
                            {incident.description && (
                              <p style={{ margin: '0.5rem 0 0 0', color: '#374151' }}>
                                {incident.description}
                              </p>
                            )}
                            <small style={{ color: '#9CA3AF', display: 'block', marginTop: '0.5rem' }}>
                              {new Date(incident.timestamp).toLocaleString()}
                            </small>
                          </div>
                          <span style={{ 
                            padding: '4px 12px', 
                            borderRadius: '20px', 
                            fontSize: '0.7rem',
                            fontWeight: 'bold',
                            backgroundColor: incident.severity === 'CRITICAL' ? '#FEE2E2' : incident.severity === 'HIGH' ? '#FEF3C7' : '#D1FAE5',
                            color: incident.severity === 'CRITICAL' ? '#B91C1C' : incident.severity === 'HIGH' ? '#B45309' : '#065F46'
                          }}>
                            {incident.severity}
                          </span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div style={{ backgroundColor: 'white', padding: '3rem', textAlign: 'center', borderRadius: '16px' }}>
                      <ShieldAlert size={48} color="#9CA3AF" />
                      <p style={{ color: '#6B7280', marginTop: '1rem' }}>Aucun incident enregistré</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </main>

      {/* Modal pour ajouter/modifier un repas */}
      {showMealModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ backgroundColor: 'white', borderRadius: '20px', padding: '2rem', width: '450px', maxWidth: '90%' }}>
            <h3 style={{ marginBottom: '1.5rem', color: '#1E3A5F' }}>{editingMeal ? 'Modifier le repas' : 'Ajouter un repas'}</h3>
            <form onSubmit={handleSaveMeal}>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', marginBottom: '0.5rem', color: '#374151', fontWeight: '500' }}>Nom du repas</label>
                <input 
                  type="text" 
                  value={mealForm.name} 
                  onChange={e => setMealForm({...mealForm, name: e.target.value})} 
                  required 
                  style={{ width: '100%', padding: '10px', border: '1px solid #D1D5DB', borderRadius: '10px', fontSize: '0.9rem' }} 
                />
              </div>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', marginBottom: '0.5rem', color: '#374151', fontWeight: '500' }}>Heure</label>
                <input 
                  type="time" 
                  value={mealForm.time} 
                  onChange={e => setMealForm({...mealForm, time: e.target.value})} 
                  required 
                  style={{ width: '100%', padding: '10px', border: '1px solid #D1D5DB', borderRadius: '10px', fontSize: '0.9rem' }} 
                />
              </div>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', marginBottom: '0.5rem', color: '#374151', fontWeight: '500' }}>Personnes attendues</label>
                <input 
                  type="number" 
                  value={mealForm.expected_people} 
                  onChange={e => setMealForm({...mealForm, expected_people: parseInt(e.target.value)})} 
                  min="1" 
                  required 
                  style={{ width: '100%', padding: '10px', border: '1px solid #D1D5DB', borderRadius: '10px', fontSize: '0.9rem' }} 
                />
              </div>
              <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem' }}>
                <button 
                  type="submit" 
                  style={{ 
                    flex: 1, 
                    padding: '12px', 
                    backgroundColor: '#1E3A5F', 
                    color: 'white', 
                    border: 'none', 
                    borderRadius: '10px', 
                    cursor: 'pointer',
                    fontWeight: '600'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#0F2B44'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#1E3A5F'}
                >
                  {editingMeal ? 'Mettre à jour' : 'Créer'}
                </button>
                <button 
                  type="button" 
                  onClick={() => setShowMealModal(false)} 
                  style={{ 
                    flex: 1, 
                    padding: '12px', 
                    backgroundColor: '#F3F4F6', 
                    color: '#374151', 
                    border: 'none', 
                    borderRadius: '10px', 
                    cursor: 'pointer',
                    fontWeight: '600'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#E5E7EB'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#F3F4F6'}
                >
                  Annuler
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------------
// FAMILY DASHBOARD (avec NotificationBell)
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

  if (loading) return <div style={{ padding: '4rem', textAlign: 'center', color: '#1E3A5F' }}><h2>Loading AI Telemetry...</h2></div>;

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
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: '#F3F4F6' }}>
      <aside style={{ width: '280px', backgroundColor: '#1E3A5F', color: 'white', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '1.5rem 2rem', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
          <Link to="/"><img src="/LOGO_AURACARE.png" alt="AuraCare Logo" style={{ height: '45px' }} /></Link>
        </div>
        <nav style={{ flex: 1, padding: '1.5rem 1rem' }}>
          <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', listStyle: 'none', padding: 0 }}>
            <li>
              <a href="#" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '12px 16px', backgroundColor: 'rgba(255,255,255,0.15)', borderRadius: '12px', color: 'white', textDecoration: 'none' }}>
                <Activity size={18} /> Overview
              </a>
            </li>
            <li>
              <a href="#" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '12px 16px', color: 'rgba(255,255,255,0.7)', textDecoration: 'none', borderRadius: '12px' }}>
                <ShieldAlert size={18} /> Incident Logs
              </a>
            </li>
          </ul>
        </nav>
        <div style={{ padding: '1.5rem', borderTop: '1px solid rgba(255,255,255,0.1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <NotificationBell token={token} />
          <button onClick={onLogout} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'rgba(255,255,255,0.7)', background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.9rem' }}>
            <LogOut size={18} /> Sign Out
          </button>
        </div>
      </aside>

      <main style={{ flex: 1, padding: '2rem', overflowY: 'auto' }}>
        {errorMsg ? (
          <div style={{ backgroundColor: 'white', padding: '3rem', borderRadius: '16px', textAlign: 'center' }}>
            <AlertCircle size={48} color="#9CA3AF" style={{ marginBottom: '1rem' }} />
            <h2 style={{ color: '#1E3A5F', marginBottom: '1rem' }}>Dashboard Unavailable</h2>
            <p style={{ color: '#6B7280' }}>{errorMsg}</p>
          </div>
        ) : (
          <>
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
              <div>
                <h1 style={{ color: '#1E3A5F', margin: 0, fontSize: '1.8rem' }}>Resident Overview</h1>
                <p style={{ color: '#6B7280', margin: '0.5rem 0 0 0' }}>Monitoring: {data?.resident_name}</p>
              </div>
              <div style={{ padding: '10px 20px', backgroundColor: 'white', borderRadius: '12px', boxShadow: '0 2px 8px rgba(0,0,0,0.05)' }}>
                <span style={{ color: '#6B7280', fontSize: '0.85rem' }}>Status: </span>
                <span style={{ color: '#10B981', fontWeight: 'bold' }}>Active & Secure</span>
              </div>
            </header>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1.5rem', marginBottom: '2rem' }}>
              <div style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: '16px', boxShadow: '0 4px 20px rgba(0,0,0,0.08)' }}>
                <h4 style={{ color: '#6B7280', margin: 0, fontSize: '0.85rem' }}>Social Interaction Score</h4>
                <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: '#1E3A5F' }}>
                  {data?.average_social_score_7d ? data.average_social_score_7d.toFixed(1) : 'N/A'}
                </div>
                <p style={{ color: '#10B981', fontSize: '0.75rem', margin: 0 }}>Last 7 Days Avg</p>
              </div>
              <div style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: '16px', boxShadow: '0 4px 20px rgba(0,0,0,0.08)' }}>
                <h4 style={{ color: '#6B7280', margin: 0, fontSize: '0.85rem' }}>Recent Incidents</h4>
                <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: '#EF4444' }}>
                  {data?.recent_incidents?.length || 0}
                </div>
                <p style={{ color: '#6B7280', fontSize: '0.75rem', margin: 0 }}>Pending review</p>
              </div>
              <div style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: '16px', boxShadow: '0 4px 20px rgba(0,0,0,0.08)' }}>
                <h4 style={{ color: '#6B7280', margin: 0, fontSize: '0.85rem' }}>Active Monitors</h4>
                <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: '#10B981' }}>7</div>
                <p style={{ color: '#6B7280', fontSize: '0.75rem', margin: 0 }}>All Zones Nominal</p>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1.5rem' }}>
              <div style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: '16px', boxShadow: '0 4px 20px rgba(0,0,0,0.08)' }}>
                <h3 style={{ color: '#1E3A5F', marginBottom: '1rem' }}>Weekly Telemetry Trends</h3>
                <div style={{ height: 300 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={tempChartData}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
                      <XAxis dataKey="name" axisLine={false} tickLine={false} />
                      <YAxis yAxisId="left" axisLine={false} tickLine={false} />
                      <YAxis yAxisId="right" orientation="right" axisLine={false} tickLine={false} />
                      <Tooltip />
                      <Legend />
                      <Line yAxisId="left" type="monotone" dataKey="social" stroke="#10B981" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 8 }} name="Social Score" />
                      <Line yAxisId="right" type="monotone" dataKey="gait" stroke="#1E3A5F" strokeWidth={3} dot={{ r: 4 }} name="Gait Speed (m/s)" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: '16px', boxShadow: '0 4px 20px rgba(0,0,0,0.08)' }}>
                <h3 style={{ color: '#1E3A5F', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <AlertCircle color="#EF4444" size={18} /> Incident Feed
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {data?.recent_incidents && data.recent_incidents.length > 0 ? (
                    data.recent_incidents.map((incident, idx) => (
                      <div key={idx} style={{ padding: '0.75rem', borderLeft: '3px solid #EF4444', backgroundColor: '#F9FAFB', borderRadius: '8px' }}>
                        <p style={{ margin: '0 0 0.25rem 0', fontWeight: 'bold', color: '#1E3A5F', fontSize: '0.85rem' }}>{incident.type_display} detected</p>
                        <p style={{ margin: 0, fontSize: '0.75rem', color: '#6B7280' }}>Zone: {incident.zone?.name || 'Unknown'}</p>
                        <p style={{ margin: 0, fontSize: '0.7rem', color: '#9CA3AF' }}>{new Date(incident.timestamp).toLocaleString()}</p>
                      </div>
                    ))
                  ) : (
                    <p style={{ color: '#6B7280', fontStyle: 'italic' }}>No recent incidents.</p>
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
// MAIN DASHBOARD ROUTER
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