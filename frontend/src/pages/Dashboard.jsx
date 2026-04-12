import { useState, useEffect } from 'react';
import { Navigate, useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { LogOut, Activity, AlertCircle, ShieldAlert, Users, HeartPulse, Upload } from 'lucide-react';
const API_BASE = 'http://127.0.0.1:8000/api';

// -----------------------------------------------------------------------------
// GAIT BADGE COMPONENT
// -----------------------------------------------------------------------------
function GaitBadge({ label, confidence }) {
  const isNormal = label === 'normal';
  return (
    <span style={{
      fontSize: '0.75rem',
      fontWeight: 'bold',
      padding: '3px 8px',
      borderRadius: '12px',
      backgroundColor: isNormal ? '#D1FAE5' : '#FEE2E2',
      color: isNormal ? '#065F46' : '#B91C1C',
    }}>
      {label?.toUpperCase()} {confidence?.toFixed(0)}%
    </span>
  );
}

// -----------------------------------------------------------------------------
// RESIDENT CARD COMPONENT
// -----------------------------------------------------------------------------
function ResidentCard({ resident, token }) {
  const [gaitData, setGaitData] = useState(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const fetchGait = async () => {
      try {
        const res = await axios.get(`${API_BASE}/gait/history/${resident.id}/`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setGaitData(res.data);
      } catch {
        setGaitData([]);
      }
    };
    fetchGait();
  }, [resident.id, token]);

  const latestGait = gaitData && gaitData.length > 0 ? gaitData[0] : null;
  const hasAlert   = gaitData && gaitData.some(g => g.alert_triggered);

  return (
    <div style={{
      backgroundColor: 'white',
      borderRadius: 'var(--border-radius)',
      boxShadow: 'var(--box-shadow)',
      borderTop: `4px solid ${resident.risk_level === 'HIGH' ? '#EF4444' : resident.risk_level === 'MEDIUM' ? '#F59E0B' : 'var(--moonstone)'}`,
      overflow: 'hidden',
    }}>
      {/* Card Header */}
      <div style={{ padding: '1.5rem', paddingBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
          <div>
            <h3 style={{ margin: 0, color: 'var(--midnight-green)' }}>{resident.name}</h3>
            <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.9rem' }}>Room: {resident.room_number} | Age: {resident.age}</p>
          </div>
          <span style={{
            fontSize: '0.8rem', fontWeight: 'bold', padding: '4px 8px', borderRadius: '12px',
            backgroundColor: resident.risk_level === 'HIGH' ? '#FEE2E2' : resident.risk_level === 'MEDIUM' ? '#FEF3C7' : '#E0F2FE',
            color: resident.risk_level === 'HIGH' ? '#B91C1C' : resident.risk_level === 'MEDIUM' ? '#B45309' : '#0369A1'
          }}>
            {resident.risk_level} RISK
          </span>
        </div>

        {/* Gait Analysis Section */}
        <div style={{
          padding: '1rem',
          backgroundColor: hasAlert ? '#FFF7ED' : '#F0FDF4',
          borderRadius: 'var(--border-radius-sm)',
          marginBottom: '1rem',
          border: `1px solid ${hasAlert ? '#FED7AA' : '#BBF7D0'}`,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <p style={{ margin: 0, fontWeight: 'bold', color: 'var(--midnight-green)', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
              🚶 Gait Analysis
              {hasAlert && <span style={{ fontSize: '0.7rem', backgroundColor: '#EF4444', color: 'white', padding: '2px 6px', borderRadius: '8px' }}>⚠ ALERT</span>}
            </p>
            {gaitData && gaitData.length > 0 && (
              <button
                onClick={() => setExpanded(!expanded)}
                style={{ fontSize: '0.75rem', color: 'var(--moonstone)', background: 'none', border: 'none', cursor: 'pointer' }}
              >
                {expanded ? 'Hide' : `View ${gaitData.length} records`}
              </button>
            )}
          </div>

          {latestGait ? (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <GaitBadge label={latestGait.label} confidence={latestGait.confidence} />
                <p style={{ margin: '0.3rem 0 0 0', fontSize: '0.75rem', color: 'var(--text-light)' }}>
                  {new Date(latestGait.recorded_at).toLocaleString()}
                </p>
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', textAlign: 'right' }}>
                <div>Stride: {latestGait.features?.stride_length?.toFixed(1)}</div>
                <div>Speed: {latestGait.features?.walking_speed?.toFixed(1)}</div>
              </div>
            </div>
          ) : (
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-light)', fontStyle: 'italic' }}>
              No gait data yet
            </p>
          )}

          {/* Expanded history */}
          {expanded && gaitData && gaitData.length > 0 && (
            <div style={{ marginTop: '0.75rem', borderTop: '1px solid #E5E7EB', paddingTop: '0.75rem' }}>
              {gaitData.slice(0, 5).map((g, idx) => (
                <div key={idx} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '0.3rem 0', borderBottom: idx < 4 ? '1px solid #F3F4F6' : 'none'
                }}>
                  <GaitBadge label={g.label} confidence={g.confidence} />
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-light)' }}>
                    {new Date(g.recorded_at).toLocaleDateString()}
                  </span>
                  {g.alert_triggered && <span style={{ fontSize: '0.7rem', color: '#EF4444' }}>⚠</span>}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Metrics */}
        <div style={{ padding: '1rem', backgroundColor: 'var(--alice-blue)', borderRadius: 'var(--border-radius-sm)', marginBottom: '1rem' }}>
          <p style={{ margin: 0, fontWeight: 'bold', color: 'var(--midnight-green)', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
            <HeartPulse size={16} color="var(--moonstone)" /> Recent Gait Sessions
          </p>
          <ul style={{ listStyle: 'none', padding: 0, margin: '0.5rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-dark)' }}>
            {gaitData && gaitData.length > 0 ? gaitData.slice(0, 3).map((g, idx) => (
              <li key={idx} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                <span style={{ color: g.label === 'normal' ? '#065F46' : '#B91C1C', fontWeight: 'bold' }}>
                  {g.label?.toUpperCase()}
                </span>
                <span style={{ color: 'var(--text-light)', fontSize: '0.8rem' }}>
                  {new Date(g.recorded_at).toLocaleDateString()}
                </span>
                <span style={{ fontWeight: 'bold' }}>{g.confidence?.toFixed(0)}%</span>
              </li>
            )) : <li style={{ color: 'var(--text-light)' }}>No gait sessions yet.</li>}
          </ul>
        </div>

        {/* Recent Incidents */}
        <div>
          <p style={{ margin: 0, fontWeight: 'bold', color: '#EF4444', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
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
    </div>
  );
}

// -----------------------------------------------------------------------------
// CAREGIVER / STAFF DASHBOARD
// -----------------------------------------------------------------------------
function StaffDashboard({ token, onLogout }) {
  const [residents, setResidents] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
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
    fetchStaffDashboard();
  }, [token, onLogout]);

  if (loading) return <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--midnight-green)' }}><h2>Loading Staff Dashboard...</h2></div>;

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
              <a href="#" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: 'var(--border-radius-sm)', color: 'var(--moonstone)', textDecoration: 'none' }}>
                <Users size={18} /> Assigned Residents
              </a>
            </li>
            <li>
              <Link to="/gait-history" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', color: 'rgba(255,255,255,0.7)', textDecoration: 'none' }}>
              <Activity size={18} /> Gait History
              </Link>
            </li>

            <li>
              <Link to="/upload-video" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', color: 'rgba(255,255,255,0.7)', textDecoration: 'none' }}>
                <Upload size={18} /> Upload Recording
              </Link>
            </li>

            <li>
              <a href="#" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', color: 'rgba(255,255,255,0.7)', textDecoration: 'none' }}>
                <ShieldAlert size={18} /> Facility Incidents
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
          </div>
        ) : (
          <>
            <header style={{ marginBottom: '3rem' }}>
              <h1 style={{ color: 'var(--midnight-green)', margin: 0 }}>Caregiver Dashboard</h1>
              <p style={{ color: 'var(--text-light)', margin: 0 }}>Monitor all assigned residents for your shift</p>
            </header>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '2rem' }}>
              {residents && residents.map(resident => (
                <ResidentCard key={resident.id} resident={resident} token={token} />
              ))}
            </div>
          </>
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
      <aside style={{ width: '260px', backgroundColor: 'var(--midnight-green)', color: 'white', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '1.5rem 2rem', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
          <Link to="/"><img src="/LOGO_AURACARE.png" alt="AuraCare Logo" style={{ height: '40px' }} /></Link>
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
                <h3 style={{ color: 'var(--midnight-green)', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <AlertCircle color="#EF4444" /> Incident Feed
                </h3>
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
// MAIN DASHBOARD ROUTER
// -----------------------------------------------------------------------------
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
    const jsonPayload = decodeURIComponent(window.atob(base64).split('').map(c =>
      '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)
    ).join(''));
    const decoded = JSON.parse(jsonPayload);
    if (decoded?.role) role = decoded.role;
  } catch (err) {
    console.error('Invalid token format', err);
  }

  if (role === 'CAREGIVER' || role === 'ADMIN') {
    return <StaffDashboard token={token} onLogout={handleLogout} />;
  }
  return <FamilyDashboard token={token} onLogout={handleLogout} />;
}
