import { useState, useEffect } from 'react';
import { Navigate, useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { LogOut, Activity, AlertCircle, ShieldAlert, Users, HeartPulse, Video, Eye } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000/api';

// -----------------------------------------------------------------------------
// INCIDENT TYPE COLOR THEME
// -----------------------------------------------------------------------------
const INCIDENT_COLORS = {
  FALL:        { bg: '#FEE2E2', border: '#DC2626', text: '#7F1D1D', badge: '#EF4444' },
  AGGRESSION:  { bg: '#FFF7ED', border: '#EA580C', text: '#7C2D12', badge: '#F97316' },
  WANDERING:   { bg: '#FEF3C7', border: '#D97706', text: '#78350F', badge: '#F59E0B' },
  DISTRESS_CRY:{ bg: '#EDE9FE', border: '#7C3AED', text: '#4C1D95', badge: '#8B5CF6' },
  CARDIAC:     { bg: '#FCE7F3', border: '#DB2777', text: '#831843', badge: '#EC4899' },
  ABSENCE:     { bg: '#E0F2FE', border: '#0284C7', text: '#0C4A6E', badge: '#0EA5E9' },
};
const DEFAULT_COLOR = { bg: '#FEE2E2', border: '#DC2626', text: '#7F1D1D', badge: '#EF4444' };
function getIncidentColor(type) { return INCIDENT_COLORS[type] || DEFAULT_COLOR; }

// -----------------------------------------------------------------------------
// CAREGIVER / STAFF DASHBOARD
// -----------------------------------------------------------------------------
function StaffDashboard({ token, onLogout }) {
  const [residents, setResidents] = useState(null);
  const [facilityIncidents, setFacilityIncidents] = useState([]);
  const [staffSection, setStaffSection] = useState('residents');
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(true);
  const [streamRunning, setStreamRunning] = useState(false);
  const [streamLoading, setStreamLoading] = useState(false);
  const [streamError, setStreamError] = useState('');
  const [streamKey, setStreamKey] = useState(0);

  useEffect(() => {
    const fetchStaffDashboard = async () => {
      try {
        const [dashboardResponse, incidentsResponse] = await Promise.all([
          axios.get(`${API_BASE}/mobile/dashboard/`, {
            headers: { Authorization: `Bearer ${token}` }
          }),
          axios.get(`${API_BASE}/mobile/facility-incidents/`, {
            headers: { Authorization: `Bearer ${token}` }
          })
        ]);
        setResidents(dashboardResponse.data);
        setFacilityIncidents(incidentsResponse.data || []);
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
    fetchStaffDashboard();
  }, [token, onLogout]);

  if (loading) return <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--midnight-green)' }}><h2>Loading Staff Dashboard...</h2></div>;

  const API_KEY = 'default-secret-key';

  const handleStartStream = async () => {
    setStreamLoading(true);
    setStreamError('');
    try {
      await axios.post(`${API_BASE}/stream/aggression/start/`, { camera: 0, device_id: 'CAM_01' }, {
        headers: { 'X-API-KEY': API_KEY }
      });
      setStreamRunning(true);
      setStreamKey(prev => prev + 1);
    } catch (e) {
      console.error('Failed to start stream', e);
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
      await axios.post(`${API_BASE}/stream/aggression/stop/`, {}, {
        headers: { 'X-API-KEY': API_KEY }
      });
      setStreamRunning(false);
    } catch (e) {
      console.error('Failed to stop stream', e);
    } finally {
      setStreamLoading(false);
    }
  };

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
                type="button"
                onClick={() => setStaffSection('residents')}
                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', width: '100%', backgroundColor: staffSection === 'residents' ? 'rgba(255,255,255,0.1)' : 'transparent', borderRadius: 'var(--border-radius-sm)', color: staffSection === 'residents' ? 'var(--moonstone)' : 'rgba(255,255,255,0.7)', textDecoration: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem' }}
              >
                <Users size={18} /> Assigned Residents
              </button>
            </li>
            <li>
              <button
                type="button"
                onClick={() => setStaffSection('incidents')}
                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', width: '100%', backgroundColor: staffSection === 'incidents' ? 'rgba(255,255,255,0.1)' : 'transparent', borderRadius: 'var(--border-radius-sm)', color: staffSection === 'incidents' ? 'var(--moonstone)' : 'rgba(255,255,255,0.7)', textDecoration: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem' }}
              >
                <ShieldAlert size={18} /> Facility Incidents
              </button>
            </li>
            <li>
              <button
                type="button"
                onClick={() => setStaffSection('livefeed')}
                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', width: '100%', backgroundColor: staffSection === 'livefeed' ? 'rgba(255,255,255,0.1)' : 'transparent', borderRadius: 'var(--border-radius-sm)', color: staffSection === 'livefeed' ? 'var(--moonstone)' : 'rgba(255,255,255,0.7)', textDecoration: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem' }}
              >
                <Video size={18} /> Live Feed
              </button>
            </li>
          </ul>
        </nav>
        <div style={{ padding: '2rem' }}>
          <button onClick={onLogout} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'rgba(255,255,255,0.7)', width: '100%', background: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem' }}>
            <LogOut size={18} /> Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main style={{ flex: 1, padding: '3rem' }}>
        <header style={{ marginBottom: '3rem' }}>
          <h1 style={{ color: 'var(--midnight-green)', margin: 0 }}>Caregiver Dashboard</h1>
          <p style={{ color: 'var(--text-light)', margin: 0 }}>
            {staffSection === 'livefeed' ? 'Monitor live aggression detection feeds' : 
             staffSection === 'incidents' ? 'View all facility incidents and history' : 
             'Monitor all assigned residents for your shift'}
          </p>
        </header>

        {staffSection === 'livefeed' ? (
          <div style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)' }}>
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
                  src={`${API_BASE}/stream/aggression/feed/`}
                  alt="Live aggression detection feed"
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
                <p style={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.85rem', marginTop: '0.5rem' }}>Camera: CAM_01 — Aggression LSTM + MediaPipe Pose</p>
              </div>
            )}

            <div style={{ marginTop: '1rem', padding: '1rem', backgroundColor: 'var(--alice-blue)', borderRadius: '8px', display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
              <div>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>Model</span>
                <p style={{ margin: 0, fontWeight: 600, color: 'var(--midnight-green)' }}>AggressionLSTM (15 features)</p>
              </div>
              <div>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>Threshold</span>
                <p style={{ margin: 0, fontWeight: 600, color: 'var(--midnight-green)' }}>70%</p>
              </div>
              <div>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>Tracking</span>
                <p style={{ margin: 0, fontWeight: 600, color: 'var(--midnight-green)' }}>Up to 3 persons</p>
              </div>
              <div>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>Auto-Report</span>
                <p style={{ margin: 0, fontWeight: 600, color: '#059669' }}>Enabled (30s cooldown)</p>
              </div>
            </div>
          </div>
        ) : staffSection === 'incidents' ? (
          <div style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)' }}>
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
                );})}
              </ul>
            ) : (
              <p style={{ color: 'var(--text-light)', margin: 0 }}>No facility incidents yet.</p>
            )}
          </div>
        ) : errorMsg ? (
          <div style={{ backgroundColor: 'white', padding: '3rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)', textAlign: 'center' }}>
            <AlertCircle size={48} color="var(--cadet-gray)" style={{ marginBottom: '1rem' }} />
            <h2 style={{ color: 'var(--midnight-green)', marginBottom: '1rem' }}>Dashboard Unavailable</h2>
            <p style={{ color: 'var(--text-light)', fontSize: '1.1rem' }}>{errorMsg}</p>
          </div>
        ) : (
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
                  {resident.incidents && resident.incidents.length > 0 ? resident.incidents.slice(0, 2).map((inc, idx) => {
                    const c = getIncidentColor(inc.type);
                    return (
                    <li key={idx} style={{ padding: '0.5rem', backgroundColor: c.bg, borderLeft: `3px solid ${c.border}`, borderRadius: '4px', marginBottom: '0.3rem' }}>
                      <strong style={{ color: c.text }}>{inc.type_display}</strong> in {inc.zone?.name || 'Unknown'}
                    </li>
                  );}) : <li style={{ color: 'var(--text-light)' }}>No recent incidents.</li>}
                </ul>
              </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

// -----------------------------------------------------------------------------
// FAMILY DASHBOARD
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
      {/* Sidebar */}
      <aside style={{ width: '260px', backgroundColor: 'var(--midnight-green)', color: 'white', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '1.5rem 2rem', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
          <Link to="/">
            <img src="/LOGO_AURACARE.png" alt="AuraCare Logo" style={{ height: '40px' }} />
          </Link>
        </div>
        <nav style={{ flex: 1, padding: '1rem' }}>
          <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', listStyle: 'none', padding: 0 }}>
            <li>
              <a href="#" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: 'var(--border-radius-sm)', color: 'var(--moonstone)', textDecoration: 'none' }}>
                <Activity size={18} /> Overview
              </a>
            </li>
            <li>
              <a href="#" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', color: 'rgba(255,255,255,0.7)', textDecoration: 'none' }}>
                <ShieldAlert size={18} /> Incident Logs
              </a>
            </li>
          </ul>
        </nav>
        <div style={{ padding: '2rem' }}>
          <button onClick={onLogout} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'rgba(255,255,255,0.7)', width: '100%', background: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem' }}>
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

            {/* Top Stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '2rem', marginBottom: '3rem' }}>
              <div style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)' }}>
                <h4 style={{ color: 'var(--text-light)', margin: 0 }}>Social Interaction Score</h4>
                <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: 'var(--midnight-green)' }}>
                  {data?.average_social_score_7d ? data.average_social_score_7d.toFixed(1) : 'N/A'}
                </div>
                <p style={{ color: 'var(--moonstone)', fontSize: '0.9rem', margin: 0 }}>Last 7 Days Avg</p>
              </div>
              <div style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)' }}>
                <h4 style={{ color: 'var(--text-light)', margin: 0 }}>Recent Incidents</h4>
                <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: '#EF4444' }}>
                  {data?.recent_incidents?.length || 0}
                </div>
                <p style={{ color: 'var(--text-light)', fontSize: '0.9rem', margin: 0 }}>Pending review</p>
              </div>
              <div style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)' }}>
                <h4 style={{ color: 'var(--text-light)', margin: 0 }}>Active Monitors</h4>
                <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: 'var(--moonstone)' }}>
                  7
                </div>
                <p style={{ color: 'var(--text-light)', fontSize: '0.9rem', margin: 0 }}>All Zones Nominal</p>
              </div>
            </div>

            {/* Charts */}
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
                      );})
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

  // Decode JWT to find the user's role
  let role = 'FAMILY';
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(window.atob(base64).split('').map(function(c) {
        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));

    const decoded = JSON.parse(jsonPayload);
    if (decoded && decoded.role) {
      role = decoded.role;
    }
  } catch (err) {
    console.error('Invalid token format', err);
  }

  // Render appropriate dashboard
  if (role === 'CAREGIVER' || role === 'ADMIN') {
    return <StaffDashboard token={token} onLogout={handleLogout} />;
  }

  return <FamilyDashboard token={token} onLogout={handleLogout} />;
}
