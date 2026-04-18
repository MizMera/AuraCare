import { useEffect, useRef, useState } from 'react';
import { Navigate, useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import {
  LogOut, Activity, AlertCircle, ShieldAlert, Users, HeartPulse, Video,
  Eye, Brain, UtensilsCrossed, Clock3, Plus, Pencil, Trash2, CheckCircle2,
} from 'lucide-react';
import SocialInteraction from './SocialInteraction';
import NotificationBell from '../components/NotificationBell';
import GaitAnalysisPanel from '../components/GaitAnalysisPanel';
import { mealService } from '../services/mealService';

const API_HOST = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';
const API_BASE = `http://${API_HOST}:8000/api`;

const navBtn = (active) => ({
  display: 'flex',
  alignItems: 'center',
  gap: '0.5rem',
  padding: '10px 15px',
  width: '100%',
  textAlign: 'left',
  border: 'none',
  cursor: 'pointer',
  fontSize: 14,
  background: 'none',
  borderRadius: 'var(--border-radius-sm)',
  backgroundColor: active ? 'rgba(255,255,255,0.15)' : 'transparent',
  color: active ? 'var(--moonstone)' : 'rgba(255,255,255,0.7)',
  fontWeight: active ? 700 : 400,
});

const INCIDENT_COLORS = {
  FALL: { bg: '#FEE2E2', border: '#DC2626', text: '#7F1D1D', badge: '#EF4444' },
  AGGRESSION: { bg: '#FFF7ED', border: '#EA580C', text: '#7C2D12', badge: '#F97316' },
  WANDERING: { bg: '#FEF3C7', border: '#D97706', text: '#78350F', badge: '#F59E0B' },
  DISTRESS_CRY: { bg: '#EDE9FE', border: '#7C3AED', text: '#4C1D95', badge: '#8B5CF6' },
  CARDIAC: { bg: '#FCE7F3', border: '#DB2777', text: '#831843', badge: '#EC4899' },
  ABSENCE: { bg: '#E0F2FE', border: '#0284C7', text: '#0C4A6E', badge: '#0EA5E9' },
};

const DEFAULT_COLOR = { bg: '#FEE2E2', border: '#DC2626', text: '#7F1D1D', badge: '#EF4444' };
const sectionCardStyle = {
  backgroundColor: 'white',
  padding: '1.5rem',
  borderRadius: 'var(--border-radius)',
  boxShadow: 'var(--box-shadow)',
};
const formInputStyle = {
  width: '100%',
  border: '1px solid #D7E3EA',
  borderRadius: '12px',
  padding: '12px 14px',
  fontSize: '0.95rem',
  color: 'var(--midnight-green)',
  backgroundColor: '#F9FCFE',
  boxSizing: 'border-box',
};
const formLabelStyle = {
  display: 'block',
  fontSize: '0.82rem',
  fontWeight: 700,
  color: 'var(--midnight-green)',
  marginBottom: '0.45rem',
};

function getIncidentColor(type) {
  return INCIDENT_COLORS[type] || DEFAULT_COLOR;
}

function MealManagementPanel({ token, role, incidents, onLogout }) {
  const [meals, setMeals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [editingMealId, setEditingMealId] = useState(null);
  const [form, setForm] = useState({ name: 'Breakfast', time: '08:00', expected_people: 4 });
  const formCardRef = useRef(null);
  const mealNameInputRef = useRef(null);
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

  useEffect(() => {
    loadMeals();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => () => {
    if (cameraPollRef.current) {
      window.clearInterval(cameraPollRef.current);
    }
  }, []);

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
      mealNameInputRef.current?.select();
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
      else if (err.response?.data) {
        const message = Object.values(err.response.data).flat().join(' ');
        setErrorMsg(message || 'Unable to save this meal schedule.');
      } else {
        setErrorMsg('Unable to save this meal schedule.');
      }
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
      if (err.response?.status === 401) onLogout();
      else setErrorMsg('Unable to delete this meal slot.');
    }
  };

  const handleStartCamera = async () => {
    setCameraLoading(true);
    setCameraError('');
    try {
      setCameraRunning(true);
      setCameraStreamKey((current) => current + 1);
      setCameraStatus((current) => ({
        ...current,
        model: 'yolo-bestt',
      }));
    } finally {
      setCameraLoading(false);
    }
  };

  const handleStopCamera = async () => {
    setCameraLoading(true);
    try {
      if (cameraPollRef.current) {
        window.clearInterval(cameraPollRef.current);
        cameraPollRef.current = null;
      }
      setCameraRunning(false);
      setCameraError('');
      setCameraStatus((current) => ({
        ...current,
        count: 0,
        active_meal: null,
        expected_people: null,
        mismatch: false,
        missing_count: 0,
      }));
      setCameraStreamKey((current) => current + 1);
    } finally {
      setCameraLoading(false);
    }
  };

  useEffect(() => {
    if (!cameraRunning) return undefined;
    const buildActiveMealSnapshot = (count) => {
      const now = new Date();
      const currentMinutes = now.getHours() * 60 + now.getMinutes();
      const activeMeal = meals.find((meal) => {
        if (!meal?.time) return false;
        const [hours, minutes] = meal.time.split(':');
        const mealMinutes = Number(hours) * 60 + Number(minutes);
        const diff = currentMinutes - mealMinutes;
        return diff >= 0 && diff <= 30;
      });

      if (!activeMeal) {
        return {
          active_meal: null,
          expected_people: null,
          mismatch: false,
          missing_count: 0,
        };
      }

      const expected = activeMeal.expected_people || 0;
      return {
        active_meal: {
          id: activeMeal.id,
          name: activeMeal.name,
          time: activeMeal.time,
        },
        expected_people: expected,
        mismatch: count < expected,
        missing_count: Math.max(0, expected - count),
      };
    };

    const pollCameraStatus = async () => {
      try {
        const countResponse = await axios.get(`${API_BASE}/person-count/`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        const count = typeof countResponse.data?.count === 'number' ? countResponse.data.count : 0;
        setCameraStatus((current) => ({
          ...current,
          count,
          model: 'yolo-bestt',
          ...buildActiveMealSnapshot(count),
        }));
        setCameraError('');
      } catch (err) {
        if (err.response?.status === 401) {
          onLogout();
        } else {
          const backendMessage = err.response?.data?.error;
          setCameraError(backendMessage || 'Unable to read Meriem’s person-count stream.');
        }
      }
    };

    pollCameraStatus();
    cameraPollRef.current = window.setInterval(pollCameraStatus, 1500);

    return () => {
      if (cameraPollRef.current) {
        window.clearInterval(cameraPollRef.current);
        cameraPollRef.current = null;
      }
    };
  }, [cameraRunning, token, onLogout, meals]);

  const mealAlerts = incidents.filter((incident) => incident.type === 'ABSENCE' || incident.meal_name);
  const totalExpected = meals.reduce((sum, meal) => sum + (meal.expected_people || 0), 0);

  if (loading) {
    return <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--midnight-green)' }}><h2>Loading meal coordination...</h2></div>;
  }

  return (
    <div style={{ display: 'grid', gap: '1.5rem' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
        <div style={{ ...sectionCardStyle, borderTop: '4px solid var(--moonstone)' }}>
          <p style={{ margin: 0, color: 'var(--text-light)', fontWeight: 600 }}>Scheduled Meals</p>
          <h2 style={{ margin: '0.45rem 0 0', color: 'var(--midnight-green)', fontSize: '2rem' }}>{meals.length}</h2>
          <p style={{ margin: '0.35rem 0 0', color: 'var(--text-light)', fontSize: '0.9rem' }}>Shared daily meal checkpoints</p>
        </div>
        <div style={{ ...sectionCardStyle, borderTop: '4px solid #0EA5E9' }}>
          <p style={{ margin: 0, color: 'var(--text-light)', fontWeight: 600 }}>Expected Attendance</p>
          <h2 style={{ margin: '0.45rem 0 0', color: 'var(--midnight-green)', fontSize: '2rem' }}>{totalExpected}</h2>
          <p style={{ margin: '0.35rem 0 0', color: 'var(--text-light)', fontSize: '0.9rem' }}>Residents planned across all meals</p>
        </div>
        <div style={{ ...sectionCardStyle, borderTop: '4px solid #F59E0B' }}>
          <p style={{ margin: 0, color: 'var(--text-light)', fontWeight: 600 }}>Absence Alerts</p>
          <h2 style={{ margin: '0.45rem 0 0', color: '#B45309', fontSize: '2rem' }}>{mealAlerts.length}</h2>
          <p style={{ margin: '0.35rem 0 0', color: 'var(--text-light)', fontSize: '0.9rem' }}>Meal-linked incidents detected so far</p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: role === 'ADMIN' ? '1.7fr 1fr' : '1fr', gap: '1.5rem' }}>
        <section style={sectionCardStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
            <div>
              <h3 style={{ margin: 0, color: 'var(--midnight-green)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <UtensilsCrossed size={18} color="var(--moonstone)" /> Meriem Meal Module
              </h3>
              <p style={{ margin: '0.35rem 0 0', color: 'var(--text-light)' }}>
                Structured meal timing and absence monitoring, restyled to match the current dashboard.
              </p>
            </div>
            <button
              type="button"
              onClick={loadMeals}
              style={{ border: 'none', borderRadius: '999px', padding: '10px 16px', backgroundColor: 'var(--alice-blue)', color: 'var(--midnight-green)', fontWeight: 700, cursor: 'pointer' }}
            >
              Refresh Schedule
            </button>
          </div>

          {meals.length > 0 ? (
            <div style={{ display: 'grid', gap: '0.9rem' }}>
              {meals.map((meal) => (
                <article key={meal.id} style={{ border: '1px solid #DCE9EF', borderRadius: '18px', padding: '1rem 1.1rem', background: 'linear-gradient(180deg, #FFFFFF 0%, #F8FBFD 100%)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
                    <div>
                      <h4 style={{ margin: 0, color: 'var(--midnight-green)' }}>{meal.name}</h4>
                      <p style={{ margin: '0.4rem 0 0', color: 'var(--text-light)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <Clock3 size={15} /> {meal.time?.slice(0, 5)} {meal.zone_name ? `• ${meal.zone_name}` : '• Auto dining zone'}
                      </p>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexWrap: 'wrap' }}>
                      <span style={{ padding: '6px 12px', borderRadius: '999px', backgroundColor: '#E0F2FE', color: '#075985', fontSize: '0.85rem', fontWeight: 700 }}>
                        {meal.expected_people} expected
                      </span>
                      {role === 'ADMIN' && (
                        <>
                          <button
                            type="button"
                            onClick={() => beginEditingMeal(meal)}
                            style={{ border: 'none', background: 'transparent', color: 'var(--midnight-green)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.35rem', fontWeight: 700 }}
                          >
                            <Pencil size={15} /> Edit
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDelete(meal.id)}
                            style={{ border: 'none', background: 'transparent', color: '#DC2626', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.35rem', fontWeight: 700 }}
                          >
                            <Trash2 size={15} /> Delete
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div style={{ borderRadius: '18px', backgroundColor: 'var(--alice-blue)', padding: '2rem', textAlign: 'center' }}>
              <UtensilsCrossed size={30} color="var(--moonstone)" style={{ marginBottom: '0.75rem', opacity: 0.8 }} />
              <p style={{ margin: 0, color: 'var(--midnight-green)', fontWeight: 700 }}>No meal schedule yet</p>
              <p style={{ margin: '0.45rem 0 0', color: 'var(--text-light)' }}>
                Add the first meal slot to activate Meriem&apos;s absence workflow.
              </p>
            </div>
          )}
        </section>

        {role === 'ADMIN' && (
          <aside ref={formCardRef} style={{ ...sectionCardStyle, alignSelf: 'start', border: editingMealId ? '2px solid #44A6B5' : '2px solid transparent', transition: 'border-color 0.2s ease' }}>
            <h3 style={{ margin: '0 0 0.35rem 0', color: 'var(--midnight-green)' }}>
              {editingMealId ? 'Edit Meal Slot' : 'Add Meal Slot'}
            </h3>
            <p style={{ margin: '0 0 1.25rem 0', color: 'var(--text-light)' }}>
              Keep Meriem&apos;s attendance model configured from the main admin experience.
            </p>

            {editingMealId && (
              <div style={{ marginBottom: '1rem', borderRadius: '14px', backgroundColor: '#ECFEFF', color: '#155E75', padding: '0.9rem 1rem', fontWeight: 700 }}>
                Editing an existing meal slot. Update the fields below, then save.
              </div>
            )}

            <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '1rem' }}>
              <label>
                <span style={formLabelStyle}>Meal Name</span>
                <input ref={mealNameInputRef} value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} placeholder="Breakfast" style={formInputStyle} required />
              </label>

              <label>
                <span style={formLabelStyle}>Scheduled Time</span>
                <input type="time" value={form.time} onChange={(event) => setForm((current) => ({ ...current, time: event.target.value }))} style={formInputStyle} required />
              </label>

              <label>
                <span style={formLabelStyle}>Expected Residents</span>
                <input type="number" min="1" value={form.expected_people} onChange={(event) => setForm((current) => ({ ...current, expected_people: event.target.value }))} style={formInputStyle} required />
              </label>

              {errorMsg && <div style={{ borderRadius: '14px', backgroundColor: '#FEF2F2', color: '#B91C1C', padding: '0.9rem 1rem', fontWeight: 600 }}>{errorMsg}</div>}

              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                <button
                  type="submit"
                  disabled={saving}
                  style={{ border: 'none', borderRadius: '12px', padding: '12px 16px', backgroundColor: 'var(--midnight-green)', color: 'white', fontWeight: 700, cursor: saving ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', gap: '0.45rem', opacity: saving ? 0.7 : 1 }}
                >
                  {editingMealId ? <CheckCircle2 size={16} /> : <Plus size={16} />}
                  {saving ? 'Saving...' : editingMealId ? 'Update Meal' : 'Create Meal'}
                </button>
                {editingMealId && (
                  <button
                    type="button"
                    onClick={resetForm}
                    style={{ border: '1px solid #D7E3EA', borderRadius: '12px', padding: '12px 16px', backgroundColor: 'white', color: 'var(--midnight-green)', fontWeight: 700, cursor: 'pointer' }}
                  >
                    Cancel
                  </button>
                )}
              </div>
            </form>
          </aside>
        )}
      </div>

      <section style={sectionCardStyle}>
        <h3 style={{ margin: '0 0 1rem 0', color: 'var(--midnight-green)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <ShieldAlert size={18} color="#F59E0B" /> Meal Alert Feed
        </h3>
        {mealAlerts.length > 0 ? (
          <div style={{ display: 'grid', gap: '0.8rem' }}>
            {mealAlerts.slice(0, 8).map((incident) => (
              <div key={incident.id} style={{ borderLeft: '4px solid #F59E0B', backgroundColor: '#FFF7ED', borderRadius: '0 14px 14px 0', padding: '1rem 1.1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                  <strong style={{ color: '#9A3412' }}>{incident.meal_name ? `${incident.meal_name} attendance alert` : incident.type_display}</strong>
                  <span style={{ fontSize: '0.82rem', color: 'var(--text-light)' }}>{new Date(incident.timestamp).toLocaleString()}</span>
                </div>
                <p style={{ margin: '0.4rem 0 0', color: 'var(--text-dark)' }}>
                  {incident.description || 'A meal attendance discrepancy was detected.'}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p style={{ margin: 0, color: 'var(--text-light)' }}>
            No meal-related alerts yet. Once absence checks create incidents, they will appear here.
          </p>
        )}
      </section>

      <section style={sectionCardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          <div>
            <h3 style={{ margin: 0, color: 'var(--midnight-green)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Eye size={18} color="var(--moonstone)" /> Meal Attendance Camera
            </h3>
            <p style={{ margin: '0.35rem 0 0', color: 'var(--text-light)' }}>
              Live people-count detection from Meriem&apos;s branch, now integrated into the main meal module.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            {!cameraRunning ? (
              <button
                type="button"
                onClick={handleStartCamera}
                disabled={cameraLoading}
                style={{ border: 'none', borderRadius: '12px', padding: '12px 18px', backgroundColor: '#059669', color: 'white', fontWeight: 700, cursor: cameraLoading ? 'not-allowed' : 'pointer', opacity: cameraLoading ? 0.7 : 1 }}
              >
                {cameraLoading ? 'Starting...' : 'Start Camera'}
              </button>
            ) : (
              <button
                type="button"
                onClick={handleStopCamera}
                disabled={cameraLoading}
                style={{ border: 'none', borderRadius: '12px', padding: '12px 18px', backgroundColor: '#DC2626', color: 'white', fontWeight: 700, cursor: cameraLoading ? 'not-allowed' : 'pointer', opacity: cameraLoading ? 0.7 : 1 }}
              >
                {cameraLoading ? 'Stopping...' : 'Stop Camera'}
              </button>
            )}
          </div>
        </div>

        {cameraError && (
          <div style={{ marginBottom: '1rem', borderRadius: '14px', backgroundColor: '#FEF2F2', color: '#B91C1C', padding: '0.9rem 1rem', fontWeight: 600 }}>
            {cameraError}
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.7fr) minmax(260px, 1fr)', gap: '1rem' }}>
          <div style={{ position: 'relative', minHeight: '340px', borderRadius: '18px', overflow: 'hidden', backgroundColor: '#091B2A', border: '1px solid #DCE9EF' }}>
            {cameraRunning ? (
              <img
                key={cameraStreamKey}
                src={`${API_BASE}/video/stream/?t=${cameraStreamKey}`}
                alt="Meriem meal attendance stream"
                onLoad={() => setCameraError('')}
                onError={() => {
                  setCameraRunning(false);
                  setCameraError('Unable to load Meriem’s video stream. If the aggression stream is active, stop it first, then try again.');
                }}
                style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block', minHeight: '340px' }}
              />
            ) : (
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'rgba(255,255,255,0.7)', textAlign: 'center', padding: '2rem' }}>
                <Video size={54} style={{ marginBottom: '1rem', opacity: 0.7 }} />
                <p style={{ margin: 0, fontSize: '1rem', fontWeight: 700 }}>Camera idle</p>
                <p style={{ margin: '0.45rem 0 0', maxWidth: '24rem' }}>
                  Start Meriem&apos;s detection stream to count people directly from the backend camera pipeline.
                </p>
              </div>
            )}
          </div>

          <div style={{ display: 'grid', gap: '1rem' }}>
            <div style={{ borderRadius: '18px', backgroundColor: '#F8FBFD', padding: '1rem 1.1rem', border: '1px solid #DCE9EF' }}>
              <p style={{ margin: 0, color: 'var(--text-light)', fontWeight: 700 }}>People Detected</p>
              <h2 style={{ margin: '0.35rem 0 0', color: 'var(--midnight-green)', fontSize: '2rem' }}>{cameraStatus.count ?? 0}</h2>
              <p style={{ margin: '0.35rem 0 0', color: 'var(--text-light)' }}>Detection model: {cameraStatus.model || 'yolo-bestt'}</p>
            </div>

            <div style={{ borderRadius: '18px', backgroundColor: cameraStatus.mismatch ? '#FFF7ED' : '#ECFDF5', padding: '1rem 1.1rem', border: `1px solid ${cameraStatus.mismatch ? '#F59E0B' : '#A7F3D0'}` }}>
              <p style={{ margin: 0, color: 'var(--text-light)', fontWeight: 700 }}>Meal Check</p>
              {cameraStatus.active_meal ? (
                <>
                  <h3 style={{ margin: '0.35rem 0 0', color: 'var(--midnight-green)' }}>{cameraStatus.active_meal.name}</h3>
                  <p style={{ margin: '0.35rem 0 0', color: 'var(--text-dark)' }}>
                    Detected {cameraStatus.count ?? 0} / Expected {cameraStatus.expected_people ?? 0}
                  </p>
                  <p style={{ margin: '0.35rem 0 0', color: cameraStatus.mismatch ? '#B45309' : '#047857', fontWeight: 700 }}>
                    {cameraStatus.mismatch ? `${cameraStatus.missing_count} resident(s) missing` : 'Count matches the scheduled meal'}
                  </p>
                </>
              ) : (
                <p style={{ margin: '0.35rem 0 0', color: 'var(--text-light)' }}>No meal is currently in its monitoring window.</p>
              )}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function StaffDashboard({ token, onLogout, role }) {
  const [residents, setResidents] = useState(null);
  const [facilityIncidents, setFacilityIncidents] = useState([]);
  const [staffSection, setStaffSection] = useState('residents');
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(true);
  const [streamRunning, setStreamRunning] = useState(false);
  const [streamLoading, setStreamLoading] = useState(false);
  const [streamError, setStreamError] = useState('');
  const [streamKey, setStreamKey] = useState(0);
  const streamPollRef = useRef(null);

  useEffect(() => {
    const fetchStaffDashboard = async () => {
      try {
        const [dashboardResponse, incidentsResponse] = await Promise.all([
          axios.get(`${API_BASE}/mobile/dashboard/`, { headers: { Authorization: `Bearer ${token}` } }),
          axios.get(`${API_BASE}/mobile/facility-incidents/`, { headers: { Authorization: `Bearer ${token}` } }),
        ]);
        setResidents(dashboardResponse.data);
        setFacilityIncidents(incidentsResponse.data || []);
      } catch (err) {
        if (err.response?.status === 401) onLogout();
        else if (err.response?.status === 404) setErrorMsg('No residents assigned to your shift yet.');
        else if (err.response?.status === 403) setErrorMsg('Access forbidden. You might not have the correct role permissions.');
        else setErrorMsg('An error occurred while fetching your dashboard.');
      } finally {
        setLoading(false);
      }
    };
    fetchStaffDashboard();
  }, [token, onLogout]);

  useEffect(() => () => {
    if (streamPollRef.current) {
      window.clearInterval(streamPollRef.current);
    }
  }, []);

  const API_KEY = 'default-secret-key';

  const handleStartStream = async () => {
    setStreamLoading(true);
    setStreamError('');
    try {
      const response = await axios.post(
        `${API_BASE}/stream/aggression/start/`,
        { camera: 0, device_id: 'CAM_01' },
        { headers: { 'X-API-KEY': API_KEY } },
      );
      if (!response.data?.running) {
        throw new Error(response.data?.error || 'Unable to keep the aggression stream running.');
      }
      setStreamRunning(true);
      setStreamError('');
      setStreamKey((prev) => prev + 1);
    } catch (e) {
      let msg = e.response?.data?.error || e.message || 'Unknown error starting stream';
      if (e.message === 'Network Error') {
        msg = 'Network Error: Cannot connect to the local Django server on port 8000. Is it running?';
      }
      setStreamError(msg);
    } finally {
      setStreamLoading(false);
    }
  };

  const handleStopStream = async () => {
    setStreamLoading(true);
    try {
      await axios.post(`${API_BASE}/stream/aggression/stop/`, {}, { headers: { 'X-API-KEY': API_KEY } });
      if (streamPollRef.current) {
        window.clearInterval(streamPollRef.current);
        streamPollRef.current = null;
      }
      setStreamRunning(false);
      setStreamError('');
    } catch (e) {
      console.error('Failed to stop stream', e);
    } finally {
      setStreamLoading(false);
    }
  };

  useEffect(() => {
    if (!streamRunning) return undefined;

    const pollStreamStatus = async () => {
      try {
        const response = await axios.get(`${API_BASE}/stream/aggression/status/`);
        if (!response.data?.running) {
          setStreamRunning(false);
          setStreamError(
            response.data?.error
            || 'Live aggression detection stopped unexpectedly. If the meal camera is open, stop it first and try again.',
          );
          return;
        }
        if (response.data?.error) {
          setStreamError(response.data.error);
        }
      } catch {
        setStreamRunning(false);
        setStreamError('Unable to read live aggression status right now.');
      }
    };

    pollStreamStatus();
    streamPollRef.current = window.setInterval(pollStreamStatus, 1500);

    return () => {
      if (streamPollRef.current) {
        window.clearInterval(streamPollRef.current);
        streamPollRef.current = null;
      }
    };
  }, [streamRunning]);

  if (loading) return <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--midnight-green)' }}><h2>Loading Staff Dashboard...</h2></div>;

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: 'var(--alice-blue)' }}>
      <aside style={{ width: '260px', backgroundColor: 'var(--midnight-green)', color: 'white', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '1.5rem 2rem', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '8px', textDecoration: 'none', color: 'white', fontSize: '1.5rem', fontWeight: 'bold' }}>
            <img src="/LOGO_AURACARE.png" alt="AuraCare Logo" style={{ height: '40px' }} />
            AuraCare
          </Link>
        </div>
        <nav style={{ flex: 1, padding: '1rem' }}>
          <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', listStyle: 'none', padding: 0 }}>
            <li><button type="button" onClick={() => setStaffSection('residents')} style={navBtn(staffSection === 'residents')}><Users size={18} /> Assigned Residents</button></li>
            <li><button type="button" onClick={() => setStaffSection('incidents')} style={navBtn(staffSection === 'incidents')}><ShieldAlert size={18} /> Facility Incidents</button></li>
            <li><button type="button" onClick={() => setStaffSection('meals')} style={navBtn(staffSection === 'meals')}><UtensilsCrossed size={18} /> Meals & Alerts</button></li>
            <li><button type="button" onClick={() => setStaffSection('gait')} style={navBtn(staffSection === 'gait')}><Activity size={18} /> Gait Analysis</button></li>
            <li><button type="button" onClick={() => setStaffSection('livefeed')} style={navBtn(staffSection === 'livefeed')}><Video size={18} /> Live Feed</button></li>
            <li><button type="button" onClick={() => setStaffSection('combi')} style={navBtn(staffSection === 'combi')}><Brain size={18} /> Social Interaction</button></li>
          </ul>
        </nav>
        <div style={{ padding: '2rem' }}>
          <div style={{ marginBottom: '1rem', padding: '0.85rem', borderRadius: '16px', backgroundColor: 'rgba(255,255,255,0.08)' }}>
            <NotificationBell token={token} />
          </div>
          <button onClick={onLogout} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'rgba(255,255,255,0.7)', width: '100%', background: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem' }}>
            <LogOut size={18} /> Sign Out
          </button>
        </div>
      </aside>

      <main style={{ flex: 1, padding: '3rem', overflowY: 'auto' }}>
        {staffSection === 'combi' ? (
          <div style={{ margin: '-3rem' }}>
            <SocialInteraction
              token={token}
              onLogout={onLogout}
              title="Social Interaction"
              description="Sarra's combined social-isolation model is now reachable from the caregiver sidebar."
            />
          </div>
        ) : (
          <div>
            <header style={{ marginBottom: '3rem' }}>
              <h1 style={{ color: 'var(--midnight-green)', margin: 0 }}>Caregiver Dashboard</h1>
              <p style={{ color: 'var(--text-light)', margin: 0 }}>
                {staffSection === 'livefeed' ? 'Monitor live aggression detection feeds' :
                  staffSection === 'gait' ? 'Review Yomna’s gait-analysis results and launch new recordings' :
                  staffSection === 'meals' ? 'Coordinate Meriem’s meal schedule and related alerts' :
                    staffSection === 'incidents' ? 'View all facility incidents and history' :
                      'Monitor all assigned residents for your shift'}
              </p>
            </header>

            {staffSection === 'gait' ? (
              <GaitAnalysisPanel token={token} onLogout={onLogout} />
            ) : staffSection === 'meals' ? (
              <MealManagementPanel token={token} role={role} incidents={facilityIncidents} onLogout={onLogout} />
            ) : staffSection === 'livefeed' ? (
              <div style={sectionCardStyle}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h3 style={{ color: 'var(--midnight-green)', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Eye size={18} color="#EA580C" /> Live Aggression Detection
                  </h3>
                  <div style={{ display: 'flex', gap: '0.75rem' }}>
                    {!streamRunning ? (
                      <button
                        onClick={handleStartStream}
                        disabled={streamLoading}
                        style={{ padding: '8px 20px', backgroundColor: '#059669', color: 'white', border: 'none', borderRadius: '8px', cursor: streamLoading ? 'not-allowed' : 'pointer', fontWeight: 600, fontSize: '0.9rem', opacity: streamLoading ? 0.6 : 1, transition: 'all 0.2s' }}
                      >
                        {streamLoading ? 'Starting...' : 'Start Stream'}
                      </button>
                    ) : (
                      <button
                        onClick={handleStopStream}
                        disabled={streamLoading}
                        style={{ padding: '8px 20px', backgroundColor: '#DC2626', color: 'white', border: 'none', borderRadius: '8px', cursor: streamLoading ? 'not-allowed' : 'pointer', fontWeight: 600, fontSize: '0.9rem', opacity: streamLoading ? 0.6 : 1, transition: 'all 0.2s' }}
                      >
                        {streamLoading ? 'Stopping...' : 'Stop Stream'}
                      </button>
                    )}
                  </div>
                </div>

                {streamError && (
                  <div style={{ backgroundColor: '#FEE2E2', color: '#B91C1C', padding: '12px', borderRadius: '8px', marginBottom: '1rem', border: '1px solid #F87171', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <AlertCircle size={20} />
                    <span style={{ fontWeight: 500 }}>{streamError}</span>
                  </div>
                )}

                {streamRunning ? (
                  <div style={{ position: 'relative', width: '100%', borderRadius: '12px', overflow: 'hidden', backgroundColor: '#000', border: '2px solid var(--midnight-green)' }}>
                    <img
                      key={streamKey}
                      src={`${API_BASE}/stream/aggression/feed/?t=${streamKey}`}
                      alt="Live aggression detection feed"
                      onLoad={() => setStreamError('')}
                      onError={() => {
                        setStreamRunning(false);
                        setStreamError('Aggression stream lost access to the webcam. If the meal camera is active, stop it first and start the aggression stream again.');
                      }}
                      style={{ width: '100%', display: 'block' }}
                    />
                    <div style={{ position: 'absolute', top: '10px', right: '10px', display: 'flex', alignItems: 'center', gap: '6px', backgroundColor: 'rgba(220, 38, 38, 0.9)', padding: '4px 12px', borderRadius: '20px' }}>
                      <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#fff', animation: 'pulse 1.5s infinite' }} />
                      <span style={{ color: 'white', fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.05em' }}>LIVE</span>
                    </div>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '400px', backgroundColor: '#111827', borderRadius: '12px', border: '2px dashed rgba(255,255,255,0.1)' }}>
                    <Video size={64} color="rgba(255,255,255,0.2)" style={{ marginBottom: '1rem' }} />
                    <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '1.1rem', margin: 0 }}>Click "Start Stream" to begin live monitoring</p>
                    <p style={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.85rem', marginTop: '0.5rem' }}>Camera: CAM_01 - Aggression LSTM + MediaPipe Pose</p>
                  </div>
                )}

                <div style={{ marginTop: '1rem', padding: '1rem', backgroundColor: 'var(--alice-blue)', borderRadius: '8px', display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
                  <div><span style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>Model</span><p style={{ margin: 0, fontWeight: 600, color: 'var(--midnight-green)' }}>AggressionLSTM (15 features)</p></div>
                  <div><span style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>Threshold</span><p style={{ margin: 0, fontWeight: 600, color: 'var(--midnight-green)' }}>70%</p></div>
                  <div><span style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>Tracking</span><p style={{ margin: 0, fontWeight: 600, color: 'var(--midnight-green)' }}>Up to 3 persons</p></div>
                  <div><span style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>Auto-Report</span><p style={{ margin: 0, fontWeight: 600, color: '#059669' }}>Enabled (30s cooldown)</p></div>
                </div>
              </div>
            ) : staffSection === 'incidents' ? (
              <div style={sectionCardStyle}>
                <h3 style={{ color: 'var(--midnight-green)', margin: '0 0 1rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <ShieldAlert size={18} color="#EF4444" /> Facility Incidents
                </h3>
                {facilityIncidents.length > 0 ? (
                  <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    {facilityIncidents.map((inc) => {
                      const c = getIncidentColor(inc.type);
                      return (
                        <li key={inc.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', padding: '0.85rem 1rem', borderRadius: '8px', backgroundColor: c.bg, borderLeft: `4px solid ${c.border}` }}>
                          <div>
                            <p style={{ margin: 0, fontWeight: 700, color: c.text, fontSize: '0.9rem' }}>
                              {inc.type_display} ({inc.severity_display})
                            </p>
                            <p style={{ margin: '0.25rem 0 0 0', color: 'var(--text-dark)', fontSize: '0.85rem' }}>
                              Zone: {inc.zone?.name || 'Unknown'}
                            </p>
                          </div>
                          <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
                            {new Date(inc.timestamp).toLocaleString()}
                          </p>
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <p style={{ color: 'var(--text-light)', margin: 0 }}>No facility incidents yet.</p>
                )}
              </div>
            ) : errorMsg ? (
              <div style={{ ...sectionCardStyle, textAlign: 'center', padding: '3rem' }}>
                <AlertCircle size={48} color="var(--cadet-gray)" style={{ marginBottom: '1rem' }} />
                <h2 style={{ color: 'var(--midnight-green)', marginBottom: '1rem' }}>Dashboard Unavailable</h2>
                <p style={{ color: 'var(--text-light)', fontSize: '1.1rem' }}>{errorMsg}</p>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '2rem' }}>
                {residents && residents.map((resident) => (
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
                        {resident.incidents && resident.incidents.length > 0 ? resident.incidents.slice(0, 2).map((inc, idx) => {
                          const c = getIncidentColor(inc.type);
                          return (
                            <li key={idx} style={{ padding: '0.5rem', backgroundColor: c.bg, borderLeft: `3px solid ${c.border}`, borderRadius: '4px', marginBottom: '0.3rem' }}>
                              <strong style={{ color: c.text }}>{inc.type_display}</strong> in {inc.zone?.name || 'Unknown'}
                            </li>
                          );
                        }) : <li style={{ color: 'var(--text-light)' }}>No recent incidents.</li>}
                      </ul>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

function FamilyDashboard({ token, onLogout }) {
  const [activePage, setActivePage] = useState('overview');
  const [data, setData] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const response = await axios.get(`${API_BASE}/mobile/activity-log/`, { headers: { Authorization: `Bearer ${token}` } });
        setData(response.data);
      } catch (err) {
        if (err.response?.status === 401) onLogout();
        else if (err.response?.status === 404) setErrorMsg('No residents assigned to your account yet.');
        else if (err.response?.status === 403) setErrorMsg('Access forbidden. You might not have the correct role permissions.');
        else setErrorMsg('An error occurred while fetching your dashboard.');
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
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '8px', textDecoration: 'none', color: 'white', fontSize: '1.5rem', fontWeight: 'bold' }}>
            <img src="/LOGO_AURACARE.png" alt="AuraCare Logo" style={{ height: '40px' }} />
            AuraCare
          </Link>
        </div>
        <nav style={{ flex: 1, padding: '1rem' }}>
          <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', listStyle: 'none', padding: 0 }}>
            <li><button onClick={() => setActivePage('overview')} style={navBtn(activePage === 'overview')}><Activity size={18} /> Overview</button></li>
            <li><button onClick={() => setActivePage('incidents')} style={navBtn(activePage === 'incidents')}><ShieldAlert size={18} /> Incident Logs</button></li>
            <li><button onClick={() => setActivePage('social')} style={navBtn(activePage === 'social')}><Brain size={18} /> Social Interaction</button></li>
          </ul>
        </nav>
        <div style={{ padding: '2rem' }}>
          <button onClick={onLogout} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'rgba(255,255,255,0.7)', width: '100%', background: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem' }}>
            <LogOut size={18} /> Sign Out
          </button>
        </div>
      </aside>

      <main style={{ flex: 1, overflowY: 'auto' }}>
        {activePage === 'social' && <SocialInteraction token={token} onLogout={onLogout} />}

        {activePage === 'overview' && (
          <div style={{ padding: '3rem' }}>
            {errorMsg ? (
              <div style={{ ...sectionCardStyle, textAlign: 'center', padding: '3rem' }}>
                <AlertCircle size={48} color="var(--cadet-gray)" style={{ marginBottom: '1rem' }} />
                <h2 style={{ color: 'var(--midnight-green)', marginBottom: '1rem' }}>Dashboard Unavailable</h2>
                <p style={{ color: 'var(--text-light)', fontSize: '1.1rem' }}>{errorMsg}</p>
                <p style={{ color: 'var(--text-light)', marginTop: '2rem' }}>Please contact an administrator to get access to specific residents.</p>
              </div>
            ) : (
              <>
                <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3rem' }}>
                  <div>
                    <h1 style={{ color: 'var(--midnight-green)', margin: 0 }}>Resident Overview</h1>
                    <p style={{ color: 'var(--text-light)', margin: 0 }}>Monitoring: {data?.resident_name}</p>
                  </div>
                  <div style={{ padding: '10px 20px', backgroundColor: 'white', borderRadius: 'var(--border-radius-sm)', boxShadow: 'var(--box-shadow)' }}>
                    <span style={{ color: 'var(--text-light)', fontSize: '0.9rem' }}>Status: </span>
                    <span style={{ color: 'var(--moonstone)', fontWeight: 'bold' }}>Active & Secure</span>
                  </div>
                </header>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '2rem', marginBottom: '3rem' }}>
                  <div style={sectionCardStyle}>
                    <h4 style={{ color: 'var(--text-light)', margin: 0 }}>Social Interaction Score</h4>
                    <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: 'var(--midnight-green)' }}>
                      {data?.average_social_score_7d ? data.average_social_score_7d.toFixed(1) : 'N/A'}
                    </div>
                    <p style={{ color: 'var(--moonstone)', fontSize: '0.9rem', margin: 0 }}>Last 7 Days Avg</p>
                  </div>
                  <div style={sectionCardStyle}>
                    <h4 style={{ color: 'var(--text-light)', margin: 0 }}>Recent Incidents</h4>
                    <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: '#EF4444' }}>{data?.recent_incidents?.length || 0}</div>
                    <p style={{ color: 'var(--text-light)', fontSize: '0.9rem', margin: 0 }}>Pending review</p>
                  </div>
                  <div style={sectionCardStyle}>
                    <h4 style={{ color: 'var(--text-light)', margin: 0 }}>Active Monitors</h4>
                    <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: 'var(--moonstone)' }}>7</div>
                    <p style={{ color: 'var(--text-light)', fontSize: '0.9rem', margin: 0 }}>All Zones Nominal</p>
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '2rem' }}>
                  <div style={{ ...sectionCardStyle, padding: '2rem' }}>
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
                  <div style={{ ...sectionCardStyle, padding: '2rem' }}>
                    <h3 style={{ color: 'var(--midnight-green)', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <AlertCircle color="#EF4444" /> Incident Feed
                    </h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                      {data?.recent_incidents && data.recent_incidents.length > 0 ? (
                        data.recent_incidents.map((incident, idx) => {
                          const c = getIncidentColor(incident.type);
                          return (
                            <div key={idx} style={{ padding: '1rem', borderLeft: `4px solid ${c.border}`, backgroundColor: c.bg, borderRadius: '0 var(--border-radius-sm) var(--border-radius-sm) 0' }}>
                              <p style={{ margin: '0 0 0.5rem 0', fontWeight: 'bold', color: c.text }}>{incident.type_display} detected</p>
                              <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-light)' }}>Zone: {incident.zone?.name || 'Unknown'}</p>
                              <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-light)' }}>{new Date(incident.timestamp).toLocaleString()}</p>
                            </div>
                          );
                        })
                      ) : (
                        <p style={{ color: 'var(--text-light)', fontStyle: 'italic' }}>No recent incidents.</p>
                      )}
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {activePage === 'incidents' && (
          <div style={{ padding: '3rem' }}>
            <header style={{ marginBottom: '3rem' }}>
              <h1 style={{ color: 'var(--midnight-green)', margin: 0 }}>Incident Logs</h1>
              <p style={{ color: 'var(--text-light)', margin: 0 }}>Full history of detected incidents</p>
            </header>
            {errorMsg ? (
              <div style={{ ...sectionCardStyle, textAlign: 'center', padding: '3rem' }}>
                <AlertCircle size={48} color="var(--cadet-gray)" style={{ marginBottom: '1rem' }} />
                <h2 style={{ color: 'var(--midnight-green)', marginBottom: '1rem' }}>Dashboard Unavailable</h2>
                <p style={{ color: 'var(--text-light)', fontSize: '1.1rem' }}>{errorMsg}</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {data?.recent_incidents && data.recent_incidents.length > 0 ? (
                  data.recent_incidents.map((incident, idx) => {
                    const c = getIncidentColor(incident.type);
                    return (
                      <div key={idx} style={{ padding: '1.5rem', borderLeft: `4px solid ${c.border}`, backgroundColor: 'white', borderRadius: '0 var(--border-radius-sm) var(--border-radius-sm) 0', boxShadow: 'var(--box-shadow)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', gap: '1rem' }}>
                          <strong style={{ color: c.text }}>{incident.type_display}</strong>
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-light)', whiteSpace: 'nowrap' }}>{new Date(incident.timestamp).toLocaleString()}</span>
                        </div>
                        <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--text-dark)' }}>{incident.description || 'No description provided.'}</p>
                        <p style={{ margin: '0.25rem 0 0', fontSize: '0.8rem', color: 'var(--text-light)' }}>Zone: {incident.zone?.name || 'Unknown'}</p>
                      </div>
                    );
                  })
                ) : (
                  <div style={{ ...sectionCardStyle, textAlign: 'center', padding: '3rem' }}>
                    <ShieldAlert size={48} color="var(--moonstone)" style={{ marginBottom: '1rem', opacity: 0.4 }} />
                    <p style={{ color: 'var(--text-light)' }}>No incidents recorded yet.</p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const token = localStorage.getItem('access_token');

  if (!token) return <Navigate to="/login" />;

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    navigate('/login');
  };

  let role = 'FAMILY';
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(window.atob(base64).split('').map((c) => `%${(`00${c.charCodeAt(0).toString(16)}`).slice(-2)}`).join(''));
    const decoded = JSON.parse(jsonPayload);
    if (decoded && decoded.role) role = decoded.role;
  } catch (err) {
    console.error('Invalid token format', err);
  }

  if (role === 'CAREGIVER' || role === 'ADMIN') {
    return <StaffDashboard token={token} onLogout={handleLogout} role={role} />;
  }
  return <FamilyDashboard token={token} onLogout={handleLogout} />;
}
