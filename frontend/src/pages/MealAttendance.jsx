// src/pages/MealAttendance.jsx
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { ArrowLeft, Camera, StopCircle, Play, Eye, AlertTriangle, UtensilsCrossed, ShieldAlert, Plus, Pencil, Trash2, Users, Calendar, Bell } from 'lucide-react';
import { mealService } from '../services/mealService';

const API_HOST = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';
const API_BASE = `http://${API_HOST}:8000/api`;

const styles = {
  page: {
    padding: '2rem',
    backgroundColor: '#F1F5F9',
    minHeight: '100vh',
  },
  container: {
    maxWidth: '1400px',
    margin: '0 auto',
  },
  
  header: {
    marginBottom: '2rem',
  },
  title: {
    fontSize: '1.75rem',
    fontWeight: '700',
    color: '#0F172A',
    margin: 0,
  },
  subtitle: {
    color: '#64748B',
    margin: '0.25rem 0 0',
  },

  // KPI Row (2 cards maintenant au lieu de 3)
  kpiRow: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: '1.5rem',
    marginBottom: '2rem',
  },
  kpiCard: (color) => ({
    background: 'white',
    borderRadius: '1rem',
    padding: '1.25rem',
    borderTop: `4px solid ${color}`,
    boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
  }),
  kpiLabel: {
    fontSize: '0.75rem',
    fontWeight: '600',
    textTransform: 'uppercase',
    color: '#64748B',
    margin: 0,
  },
  kpiValue: {
    fontSize: '2rem',
    fontWeight: '700',
    color: '#1E293B',
    margin: '0.5rem 0 0',
  },

  cameraSection: {
    display: 'grid',
    gridTemplateColumns: '1.8fr 1fr',
    gap: '1.5rem',
    marginBottom: '2rem',
  },
  videoCard: {
    background: 'white',
    borderRadius: '1rem',
    padding: '1rem',
    boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
    border: '1px solid #E2E8F0',
  },
  videoTitle: {
    fontSize: '0.875rem',
    fontWeight: '600',
    color: '#1E293B',
    marginBottom: '0.75rem',
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  },
  videoContainer: {
    background: '#0F172A',
    borderRadius: '0.75rem',
    overflow: 'hidden',
    aspectRatio: '16/9',
    position: 'relative',
  },
  videoImage: {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
  },
  videoPlaceholder: {
    position: 'absolute',
    inset: 0,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    color: 'rgba(255,255,255,0.6)',
    textAlign: 'center',
    padding: '1.5rem',
  },
  controlsCard: {
    background: 'white',
    borderRadius: '1rem',
    padding: '1rem',
    boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
    border: '1px solid #E2E8F0',
  },
  buttonGroup: {
    display: 'flex',
    gap: '0.75rem',
    marginBottom: '1rem',
  },
  btnStart: {
    flex: 1,
    background: '#10B981',
    color: 'white',
    border: 'none',
    padding: '0.75rem',
    borderRadius: '0.75rem',
    fontWeight: '600',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.5rem',
  },
  btnStop: {
    flex: 1,
    background: '#EF4444',
    color: 'white',
    border: 'none',
    padding: '0.75rem',
    borderRadius: '0.75rem',
    fontWeight: '600',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.5rem',
  },
  statsBox: {
    background: '#F8FAFC',
    borderRadius: '0.75rem',
    padding: '0.75rem',
    marginBottom: '1rem',
    textAlign: 'center',
  },
  statsNumber: {
    fontSize: '1.75rem',
    fontWeight: '700',
    color: '#1E293B',
    margin: '0.25rem 0 0',
  },
  twoColumns: {
    display: 'grid',
    gridTemplateColumns: '1fr 0.9fr',
    gap: '1.5rem',
    marginBottom: '2rem',
  },
  card: {
    background: 'white',
    borderRadius: '1rem',
    padding: '1.25rem',
    boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
    border: '1px solid #E2E8F0',
  },
  cardTitle: {
    fontSize: '0.875rem',
    fontWeight: '600',
    color: '#1E293B',
    marginBottom: '1rem',
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    paddingBottom: '0.75rem',
    borderBottom: '1px solid #E2E8F0',
  },
  mealList: {
    maxHeight: '400px',
    overflowY: 'auto',
  },
  mealItem: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '0.75rem 0',
    borderBottom: '1px solid #F1F5F9',
  },
  mealName: {
    fontWeight: '600',
    color: '#1E293B',
    fontSize: '0.875rem',
  },
  mealTime: {
    color: '#64748B',
    fontSize: '0.75rem',
    marginLeft: '0.5rem',
  },
  mealBadge: {
    background: '#E0F2FE',
    color: '#0369A1',
    padding: '0.25rem 0.5rem',
    borderRadius: '9999px',
    fontSize: '0.7rem',
    fontWeight: '600',
    marginLeft: '0.5rem',
  },
  formInput: {
    width: '100%',
    border: '1px solid #E2E8F0',
    borderRadius: '0.75rem',
    padding: '0.75rem',
    fontSize: '0.875rem',
    marginBottom: '0.75rem',
    boxSizing: 'border-box',
  },
  btnSubmit: {
    width: '100%',
    background: '#1E293B',
    color: 'white',
    border: 'none',
    padding: '0.75rem',
    borderRadius: '0.75rem',
    fontWeight: '600',
    cursor: 'pointer',
    marginTop: '0.5rem',
  },
  btnCancel: {
    width: '100%',
    background: '#F1F5F9',
    color: '#475569',
    border: 'none',
    padding: '0.75rem',
    borderRadius: '0.75rem',
    fontWeight: '600',
    cursor: 'pointer',
    marginTop: '0.5rem',
  },
  alertCard: {
    background: 'white',
    borderRadius: '1rem',
    padding: '1.25rem',
    boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
    border: '1px solid #E2E8F0',
  },
  alertList: {
    maxHeight: '300px',
    overflowY: 'auto',
  },
  alertItem: {
    borderLeft: '4px solid #F59E0B',
    background: '#FFF7ED',
    padding: '0.75rem',
    marginBottom: '0.75rem',
    borderRadius: '0 0.5rem 0.5rem 0',
  },
  alertTitle: {
    fontWeight: '700',
    color: '#9A3412',
    fontSize: '0.8rem',
  },
  alertDate: {
    fontSize: '0.65rem',
    color: '#64748B',
  },
  alertDesc: {
    margin: '0.25rem 0 0',
    fontSize: '0.75rem',
    color: '#475569',
  },
};

export default function MealAttendance({ token, role, onLogout }) {
  const [meals, setMeals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [editingMealId, setEditingMealId] = useState(null);
  const [form, setForm] = useState({ name: 'Breakfast', time: '08:00', expected_people: 4 });
  const formCardRef = useRef(null);
  const mealNameInputRef = useRef(null);
  const [incidents, setIncidents] = useState([]);
  
  const [cameraRunning, setCameraRunning] = useState(false);
  const [cameraLoading, setCameraLoading] = useState(false);
  const [cameraError, setCameraError] = useState('');
  const [cameraStatus, setCameraStatus] = useState({
    count: 0,
    active_meal: null,
    expected_people: null,
    mismatch: false,
    missing_count: 0,
    model: 'yolo-bestt',
  });
  const [cameraStreamKey, setCameraStreamKey] = useState(0);
  const cameraPollRef = useRef(null);

  const authHeader = { Authorization: `Bearer ${token}` };

  // ========== GARDEZ TOUTES VOS FONCTIONS EXISTANTES ICI ==========
  const loadMeals = async () => {
    try {
      setErrorMsg('');
      const data = await mealService.getAll(token);
      setMeals(data || []);
    } catch (err) {
      if (err.response?.status === 401) onLogout();
      else setErrorMsg('Unable to load the meal schedule right now.');
    } finally {
      setLoading(false);
    }
  };

  const loadIncidents = async () => {
    try {
      const response = await axios.get(`${API_BASE}/incidents/`, { headers: authHeader });
      const mealAlerts = (response.data || []).filter(inc => inc.type === 'ABSENCE');
      setIncidents(mealAlerts);
    } catch (err) {
      console.error('Failed to load incidents', err);
    }
  };

  const handleStartCamera = async () => {
    setCameraLoading(true);
    setCameraError('');
    try {
      const response = await axios.post(`${API_BASE}/meal-attendance/start/`, { camera: 0 }, { headers: authHeader });
      if (response.data?.error) {
        setCameraError(response.data.error);
        setCameraRunning(false);
      } else {
        setCameraRunning(true);
        setCameraStreamKey(prev => prev + 1);
      }
    } catch (err) {
      setCameraError(err.response?.data?.error || 'Unable to start camera.');
      setCameraRunning(false);
    } finally {
      setCameraLoading(false);
    }
  };

  const handleStopCamera = async () => {
    setCameraLoading(true);
    try {
      await axios.post(`${API_BASE}/meal-attendance/stop/`, {}, { headers: authHeader });
      if (cameraPollRef.current) {
        window.clearInterval(cameraPollRef.current);
        cameraPollRef.current = null;
      }
      setCameraRunning(false);
      setCameraStatus({
        count: 0,
        active_meal: null,
        expected_people: null,
        mismatch: false,
        missing_count: 0,
        model: 'yolo-bestt',
      });
      setCameraStreamKey(prev => prev + 1);
    } catch (err) {
      setCameraError(err.response?.data?.error || 'Could not stop camera.');
    } finally {
      setCameraLoading(false);
    }
  };

  const resetForm = () => {
    setEditingMealId(null);
    setForm({ name: 'Breakfast', time: '08:00', expected_people: 4 });
  };

  const beginEditingMeal = (meal) => {
    setEditingMealId(meal.id);
    setErrorMsg('');
    setForm({
      name: meal.name,
      time: meal.time?.slice(0, 5) || '08:00',
      expected_people: meal.expected_people,
    });
    window.requestAnimationFrame(() => {
      formCardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      mealNameInputRef.current?.focus();
    });
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setErrorMsg('');
    try {
      const payload = {
        name: form.name.trim(),
        time: form.time,
        expected_people: Number(form.expected_people),
      };
      if (editingMealId) await mealService.update(editingMealId, payload, token);
      else await mealService.create(payload, token);
      await loadMeals();
      resetForm();
    } catch (err) {
      if (err.response?.status === 401) onLogout();
      else setErrorMsg('Unable to save this meal schedule.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (mealId) => {
    if (!window.confirm('Delete this meal slot from the schedule?')) return;
    try {
      await mealService.delete(mealId, token);
      await loadMeals();
      if (editingMealId === mealId) resetForm();
    } catch (err) {
      setErrorMsg('Unable to delete this meal slot.');
    }
  };

  const getActiveMeal = () => {
    const now = new Date();
    const currentMinutes = now.getHours() * 60 + now.getMinutes();
    return meals.find(meal => {
      if (!meal?.time) return false;
      const [hours, minutes] = meal.time.split(':');
      const mealMinutes = Number(hours) * 60 + Number(minutes);
      return currentMinutes === mealMinutes;
    });
  };

  useEffect(() => {
    loadMeals();
    loadIncidents();
  }, []);

  useEffect(() => {
    if (!cameraRunning) return;
    const pollCameraStatus = async () => {
      try {
        const countResponse = await axios.get(`${API_BASE}/person-count/`, { headers: authHeader });
        const count = typeof countResponse.data?.count === 'number' ? countResponse.data.count : 0;
        const activeMeal = getActiveMeal();
        await loadIncidents();
        setCameraStatus({
          count,
          model: 'yolo-bestt',
          active_meal: activeMeal ? { id: activeMeal.id, name: activeMeal.name, time: activeMeal.time } : null,
          expected_people: activeMeal?.expected_people || null,
          mismatch: activeMeal ? count < activeMeal.expected_people : false,
          missing_count: activeMeal ? Math.max(0, activeMeal.expected_people - count) : 0,
        });
      } catch (err) {
        if (err.response?.status === 401) onLogout();
        else setCameraError('Unable to read person-count.');
      }
    };
    pollCameraStatus();
    cameraPollRef.current = window.setInterval(pollCameraStatus, 1500);
    return () => {
      if (cameraPollRef.current) window.clearInterval(cameraPollRef.current);
    };
  }, [cameraRunning, token, meals]);

  const mealAlerts = incidents;

  if (loading) {
    return <div style={{ padding: '4rem', textAlign: 'center' }}><h2>Loading meal coordination...</h2></div>;
  }

  return (
    <div style={styles.page}>
      <div style={styles.container}>
        
        {/* HEADER - sans le lien de retour */}
        <div style={styles.header}>
          <h1 style={styles.title}>Meal Attendance Monitor</h1>
          <p style={styles.subtitle}>Live people-count detection and meal absence alerts (checks at T+1 minute)</p>
        </div>

        {/* KPI ROW - seulement 2 cartes (Scheduled Meals + Absence Alerts) */}
        <div style={styles.kpiRow}>
          <div style={styles.kpiCard('#44A6B5')}>
            <p style={styles.kpiLabel}>Scheduled Meals</p>
            <p style={styles.kpiValue}>{meals.length}</p>
          </div>
          <div style={styles.kpiCard('#F59E0B')}>
            <p style={styles.kpiLabel}>Absence Alerts</p>
            <p style={{ ...styles.kpiValue, color: '#B45309' }}>{mealAlerts.length}</p>
          </div>
        </div>

        {/* CAMERA SECTION */}
        <div style={styles.cameraSection}>
          <div style={styles.videoCard}>
            <div style={styles.videoTitle}>
              <Camera size={16} color="#44A6B5" /> Live Camera Feed
            </div>
            <div style={styles.videoContainer}>
              {cameraRunning ? (
                <img
                  key={cameraStreamKey}
                  src={`${API_BASE}/meal-attendance/feed/?t=${cameraStreamKey}`}
                  alt="Stream"
                  style={styles.videoImage}
                  onError={() => {
                    setCameraRunning(false);
                    setCameraError('Unable to load video stream.');
                  }}
                />
              ) : (
                <div style={styles.videoPlaceholder}>
                  <Camera size={48} style={{ marginBottom: '1rem', opacity: 0.5 }} />
                  <p style={{ fontWeight: 600 }}>Camera idle</p>
                  <p style={{ fontSize: '0.8rem' }}>Click "Start Camera" to begin</p>
                </div>
              )}
            </div>
          </div>

          <div style={styles.controlsCard}>
            <div style={styles.buttonGroup}>
              {!cameraRunning ? (
                <button onClick={handleStartCamera} disabled={cameraLoading} style={styles.btnStart}>
                  <Play size={14} /> Start Camera
                </button>
              ) : (
                <button onClick={handleStopCamera} disabled={cameraLoading} style={styles.btnStop}>
                  <StopCircle size={14} /> Stop Camera
                </button>
              )}
            </div>

            <div style={styles.statsBox}>
              <p style={styles.kpiLabel}>PEOPLE DETECTED</p>
              <p style={styles.statsNumber}>{cameraStatus.count ?? 0}</p>
              <p style={{ fontSize: '0.7rem', color: '#64748B', margin: '0.25rem 0 0' }}>
                Model: {cameraStatus.model}
              </p>
            </div>

            <div style={{ ...styles.statsBox, background: cameraStatus.mismatch ? '#FFF7ED' : '#F8FAFC' }}>
              <p style={styles.kpiLabel}>MEAL CHECK</p>
              {cameraStatus.active_meal ? (
                <>
                  <p style={{ fontWeight: '600', margin: '0.25rem 0 0' }}>{cameraStatus.active_meal.name}</p>
                  <p style={{ fontSize: '0.8rem', margin: '0.25rem 0 0' }}>
                    {cameraStatus.count} / {cameraStatus.expected_people}
                  </p>
                  <p style={{ fontSize: '0.7rem', fontWeight: '600', color: cameraStatus.mismatch ? '#B45309' : '#047857', margin: '0.25rem 0 0' }}>
                    {cameraStatus.mismatch ? `${cameraStatus.missing_count} missing` : 'Complete'}
                  </p>
                </>
              ) : (
                <p style={{ fontSize: '0.8rem', margin: '0.5rem 0 0' }}>No meal in monitoring window</p>
              )}
            </div>

            {cameraError && (
              <div style={{ marginTop: '0.75rem', padding: '0.5rem', background: '#FEF2F2', borderRadius: '0.5rem', color: '#B91C1C', fontSize: '0.7rem' }}>
                <AlertTriangle size={12} style={{ marginRight: '0.25rem' }} /> {cameraError}
              </div>
            )}
          </div>
        </div>

        {/* TWO COLUMNS: MEAL SCHEDULE + ADD MEAL (ADMIN ONLY) */}
        <div style={styles.twoColumns}>
          <div style={styles.card}>
            <div style={styles.cardTitle}>
              <Calendar size={16} color="#44A6B5" /> Meal Schedule
              {role === 'ADMIN' && <span style={{ fontSize: '0.65rem', color: '#10B981', marginLeft: '0.5rem' }}>(Admin: edit/delete)</span>}
              {role === 'CAREGIVER' && <span style={{ fontSize: '0.65rem', color: '#64748B', marginLeft: '0.5rem' }}>(Read only)</span>}
            </div>
            <div style={styles.mealList}>
              {meals.map(meal => (
                <div key={meal.id} style={styles.mealItem}>
                  <div>
                    <span style={styles.mealName}>{meal.name}</span>
                    <span style={styles.mealTime}>{meal.time?.slice(0, 5)}</span>
                    <span style={styles.mealBadge}>{meal.expected_people} expected</span>
                  </div>
                  {role === 'ADMIN' && (
                    <div>
                      <button onClick={() => beginEditingMeal(meal)} style={{ background: 'none', border: 'none', cursor: 'pointer', marginRight: '8px', color: '#3B82F6' }}>
                        <Pencil size={14} />
                      </button>
                      <button onClick={() => handleDelete(meal.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#EF4444' }}>
                        <Trash2 size={14} />
                      </button>
                    </div>
                  )}
                </div>
              ))}
              {meals.length === 0 && <p style={{ textAlign: 'center', color: '#64748B', padding: '2rem' }}>No meals scheduled yet.</p>}
            </div>
          </div>

          {role === 'ADMIN' && (
            <div ref={formCardRef} style={styles.card}>
              <div style={styles.cardTitle}>
                <Plus size={16} color="#10B981" /> {editingMealId ? 'Edit Meal' : 'Add New Meal'}
              </div>
              <form onSubmit={handleSubmit}>
                <input
                  ref={mealNameInputRef}
                  type="text"
                  placeholder="Meal name"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  style={styles.formInput}
                  required
                />
                <input
                  type="time"
                  value={form.time}
                  onChange={(e) => setForm({ ...form, time: e.target.value })}
                  style={styles.formInput}
                  required
                />
                <input
                  type="number"
                  min="1"
                  placeholder="Expected residents"
                  value={form.expected_people}
                  onChange={(e) => setForm({ ...form, expected_people: e.target.value })}
                  style={styles.formInput}
                  required
                />
                {errorMsg && <div style={{ color: '#B91C1C', fontSize: '0.7rem', marginBottom: '0.5rem' }}>{errorMsg}</div>}
                <button type="submit" disabled={saving} style={styles.btnSubmit}>
                  {saving ? 'Saving...' : (editingMealId ? 'Update Meal' : 'Create Meal')}
                </button>
                {editingMealId && (
                  <button type="button" onClick={resetForm} style={styles.btnCancel}>
                    Cancel
                  </button>
                )}
              </form>
            </div>
          )}
        </div>

        {/* ALERT FEED */}
        <div style={styles.alertCard}>
          <div style={styles.cardTitle}>
            <Bell size={16} color="#F59E0B" /> Meal Alert Feed
            {cameraRunning && <span style={{ fontSize: '0.6rem', color: '#10B981', marginLeft: '0.5rem' }}>● Auto-refresh</span>}
          </div>
          <div style={styles.alertList}>
            {mealAlerts.length > 0 ? (
              mealAlerts.slice(0, 15).map(inc => (
                <div key={inc.id} style={styles.alertItem}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <span style={styles.alertTitle}>⚠️ {inc.meal_name || 'Meal'} attendance alert</span>
                    <span style={styles.alertDate}>{new Date(inc.timestamp).toLocaleString()}</span>
                  </div>
                  <p style={styles.alertDesc}>{inc.description || 'Attendance issue detected'}</p>
                </div>
              ))
            ) : (
              <p style={{ textAlign: 'center', color: '#64748B', padding: '2rem' }}>No meal-related alerts yet.</p>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}