import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { LogOut, Users, ShieldAlert, Activity, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const API_BASE = 'http://127.0.0.1:8000/api';

function GaitBadge({ label, confidence }) {
  const isNormal = label === 'normal';
  return (
    <span style={{
      fontSize: '0.75rem',
      fontWeight: 'bold',
      padding: '3px 10px',
      borderRadius: '12px',
      backgroundColor: isNormal ? '#D1FAE5' : '#FEE2E2',
      color: isNormal ? '#065F46' : '#B91C1C',
    }}>
      {label?.toUpperCase()} {confidence?.toFixed(0)}%
    </span>
  );
}

function ResidentGaitCard({ resident }) {
  const [expanded, setExpanded] = useState(false);
  const obs = resident.observations || [];
  const latest = obs[0];
  const hasAlert = obs.some(o => o.alert_triggered);

  // Build chart data from observations (last 7)
  const chartData = obs.slice(0, 7).reverse().map((o, idx) => ({
    name: new Date(o.recorded_at).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }),
    confidence: parseFloat(o.confidence.toFixed(1)),
    status: o.label === 'normal' ? 1 : 0,
  }));

  const abnormalCount = obs.filter(o => o.label === 'abnormal').length;
  const normalCount   = obs.filter(o => o.label === 'normal').length;

  return (
    <div style={{
      backgroundColor: 'white',
      borderRadius: 'var(--border-radius)',
      boxShadow: 'var(--box-shadow)',
      marginBottom: '1.5rem',
      overflow: 'hidden',
      border: hasAlert ? '1px solid #FCA5A5' : '1px solid #E5E7EB',
    }}>
      {/* Header */}
      <div style={{
        padding: '1.25rem 1.5rem',
        borderLeft: `5px solid ${resident.risk_level === 'HIGH' ? '#EF4444' : resident.risk_level === 'MEDIUM' ? '#F59E0B' : '#10B981'}`,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        backgroundColor: hasAlert ? '#FFF7ED' : 'white',
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <h3 style={{ margin: 0, color: 'var(--midnight-green)', fontSize: '1.1rem' }}>{resident.resident_name}</h3>
            {hasAlert && (
              <span style={{ fontSize: '0.7rem', backgroundColor: '#EF4444', color: 'white', padding: '2px 8px', borderRadius: '8px', fontWeight: 'bold' }}>
                ⚠ GAIT ALERT
              </span>
            )}
          </div>
          <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-light)' }}>
            Room: {resident.room_number} | Age: {resident.age} | Risk: {resident.risk_level}
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
          {/* Stats */}
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#EF4444' }}>{abnormalCount}</div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-light)' }}>Abnormal</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#10B981' }}>{normalCount}</div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-light)' }}>Normal</div>
          </div>

          {/* Latest */}
          {latest && <GaitBadge label={latest.label} confidence={latest.confidence} />}

          {/* Expand button */}
          <button
            onClick={() => setExpanded(!expanded)}
            style={{ background: 'none', border: '1px solid #E5E7EB', borderRadius: '8px', padding: '6px 12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem', color: 'var(--text-light)' }}
          >
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            {expanded ? 'Hide' : 'Details'}
          </button>
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div style={{ padding: '1.5rem', borderTop: '1px solid #F3F4F6' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>

            {/* Chart */}
            <div>
              <h4 style={{ margin: '0 0 1rem 0', color: 'var(--midnight-green)', fontSize: '0.9rem' }}>Gait Confidence Trend</h4>
              <div style={{ height: 180 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F3F4F6" />
                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 11 }} />
                    <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(val) => `${val}%`} />
                    <Line type="monotone" dataKey="confidence" stroke="#0EA5E9" strokeWidth={2} dot={{ r: 3 }} name="Confidence" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* History table */}
            <div>
              <h4 style={{ margin: '0 0 1rem 0', color: 'var(--midnight-green)', fontSize: '0.9rem' }}>Recent Sessions</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '180px', overflowY: 'auto' }}>
                {obs.map((o, idx) => (
                  <div key={idx} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '0.5rem 0.75rem',
                    backgroundColor: o.label === 'abnormal' ? '#FFF7F7' : '#F0FDF4',
                    borderRadius: '6px',
                    fontSize: '0.8rem',
                  }}>
                    <GaitBadge label={o.label} confidence={o.confidence} />
                    <span style={{ color: 'var(--text-light)' }}>
                      {new Date(o.recorded_at).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                    </span>
                    {o.alert_triggered && <span style={{ color: '#EF4444', fontSize: '0.7rem' }}>⚠ Alert</span>}
                    {o.snapshot && (
                      <img
                        src={`http://127.0.0.1:8000${o.snapshot}`}
                        alt="gait snapshot"
                        style={{ width: '60px', height: '40px', objectFit: 'cover', borderRadius: '4px', cursor: 'pointer' }}
                        onClick={() => window.open(`http://127.0.0.1:8000${o.snapshot}`, '_blank')}
                      />
                    )}
                    </div>
                ))}
              </div>
            </div>
          </div>

          {/* Latest features */}
          {latest?.features && (
            <div style={{ marginTop: '1rem', padding: '1rem', backgroundColor: '#F8FAFC', borderRadius: '8px' }}>
              <h4 style={{ margin: '0 0 0.75rem 0', color: 'var(--midnight-green)', fontSize: '0.85rem' }}>Latest Gait Features</h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem' }}>
                {Object.entries(latest.features).map(([key, val]) => (
                  <div key={key} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', padding: '0.3rem 0', borderBottom: '1px solid #E5E7EB' }}>
                    <span style={{ color: 'var(--text-light)' }}>{key.replace('_', ' ')}</span>
                    <span style={{ fontWeight: 'bold', color: 'var(--midnight-green)' }}>{val.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function GaitHistory() {
  const navigate = useNavigate();
  const token = localStorage.getItem('access_token');
  const [residents, setResidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState('');
  const [filter, setFilter] = useState('all'); // all, alert, normal, abnormal

  useEffect(() => {
    if (!token) { navigate('/login'); return; }
    const fetch = async () => {
      try {
        const res = await axios.get(`${API_BASE}/gait/all/`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setResidents(res.data);
      } catch (err) {
        if (err.response?.status === 401) navigate('/login');
        else setErrorMsg('Could not load gait history.');
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [token, navigate]);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    navigate('/login');
  };

  const filtered = residents.filter(r => {
    if (filter === 'alert')    return r.observations.some(o => o.alert_triggered);
    if (filter === 'abnormal') return r.observations[0]?.label === 'abnormal';
    if (filter === 'normal')   return r.observations[0]?.label === 'normal';
    return true;
  });

  const totalAlerts   = residents.filter(r => r.observations.some(o => o.alert_triggered)).length;
  const totalAbnormal = residents.filter(r => r.observations[0]?.label === 'abnormal').length;
  const totalNormal   = residents.filter(r => r.observations[0]?.label === 'normal').length;

  if (loading) return <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--midnight-green)' }}><h2>Loading Gait History...</h2></div>;

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: 'var(--alice-blue)' }}>
      {/* Sidebar */}
      <aside style={{ width: '260px', backgroundColor: 'var(--midnight-green)', color: 'white', display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
        <div style={{ padding: '1.5rem 2rem', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
          <Link to="/"><img src="/LOGO_AURACARE.png" alt="AuraCare Logo" style={{ height: '40px' }} /></Link>
        </div>
        <nav style={{ flex: 1, padding: '1rem' }}>
          <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', listStyle: 'none', padding: 0 }}>
            <li>
              <Link to="/dashboard" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', color: 'rgba(255,255,255,0.7)', textDecoration: 'none' }}>
                <Users size={18} /> Assigned Residents
              </Link>
            </li>
            <li>
              <Link to="/gait-history" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: 'var(--border-radius-sm)', color: 'var(--moonstone)', textDecoration: 'none' }}>
                <Activity size={18} /> Gait History
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
          <button onClick={handleLogout} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'rgba(255,255,255,0.7)', width: '100%', background: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem' }}>
            <LogOut size={18} /> Sign Out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main style={{ flex: 1, padding: '3rem', overflowY: 'auto' }}>
        <header style={{ marginBottom: '2rem' }}>
          <h1 style={{ color: 'var(--midnight-green)', margin: 0 }}>Gait Analysis History</h1>
          <p style={{ color: 'var(--text-light)', margin: 0 }}>Full gait monitoring history for all assigned residents</p>
        </header>

        {/* Stats */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1.5rem', marginBottom: '2rem' }}>
          <div style={{ backgroundColor: 'white', padding: '1.25rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)', borderLeft: '4px solid #EF4444' }}>
            <h4 style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.85rem' }}>Active Alerts</h4>
            <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#EF4444' }}>{totalAlerts}</div>
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-light)' }}>Residents with gait alert</p>
          </div>
          <div style={{ backgroundColor: 'white', padding: '1.25rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)', borderLeft: '4px solid #F59E0B' }}>
            <h4 style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.85rem' }}>Last Abnormal</h4>
            <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#F59E0B' }}>{totalAbnormal}</div>
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-light)' }}>Latest session abnormal</p>
          </div>
          <div style={{ backgroundColor: 'white', padding: '1.25rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)', borderLeft: '4px solid #10B981' }}>
            <h4 style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.85rem' }}>Last Normal</h4>
            <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#10B981' }}>{totalNormal}</div>
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-light)' }}>Latest session normal</p>
          </div>
        </div>

        {/* Filter */}
        <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '2rem' }}>
          {['all', 'alert', 'abnormal', 'normal'].map(f => (
            <button key={f} onClick={() => setFilter(f)} style={{
              padding: '6px 16px', borderRadius: '20px', border: 'none', cursor: 'pointer', fontSize: '0.85rem', fontWeight: filter === f ? 'bold' : 'normal',
              backgroundColor: filter === f ? 'var(--midnight-green)' : 'white',
              color: filter === f ? 'white' : 'var(--text-light)',
              boxShadow: 'var(--box-shadow)',
            }}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>

        {/* Error */}
        {errorMsg && (
          <div style={{ backgroundColor: '#FEE2E2', padding: '1rem', borderRadius: '8px', color: '#B91C1C', marginBottom: '1rem' }}>
            <AlertCircle size={16} style={{ marginRight: '0.5rem' }} /> {errorMsg}
          </div>
        )}

        {/* Resident cards */}
        {filtered.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-light)' }}>
            <Activity size={48} style={{ marginBottom: '1rem', opacity: 0.3 }} />
            <p>No gait data found for this filter.</p>
          </div>
        ) : (
          filtered.map(resident => (
            <ResidentGaitCard key={resident.resident_id} resident={resident} />
          ))
        )}
      </main>
    </div>
  );
}
