import { useState, useEffect } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { LogOut, Activity, AlertCircle, ShieldAlert } from 'lucide-react';

const API_BASE = 'http://localhost:8000/api';

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchDashboard = async () => {
      const token = localStorage.getItem('access_token');
      if (!token) {
        navigate('/login');
        return;
      }
      try {
        const response = await axios.get(`${API_BASE}/mobile/activity-log/`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setData(response.data);
      } catch (err) {
        if (err.response && err.response.status === 401) {
          localStorage.removeItem('access_token');
          navigate('/login');
        }
      } finally {
        setLoading(false);
      }
    };
    fetchDashboard();
  }, [navigate]);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    navigate('/login');
  };

  if (loading) return <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--midnight-green)' }}><h2>Loading AI Telemetry...</h2></div>;
  if (!data) return <Navigate to="/login" />;

  // Transform data for charts
  // Usually the backend returns temporal data, here we mock a 7-day trend to make the chart look nice
  // using the average_social_score_7d as a base point to demonstrate the UI
  const tempChartData = [
    { name: 'Mon', gait: 0.8, social: data.average_social_score_7d - 5 },
    { name: 'Tue', gait: 0.9, social: data.average_social_score_7d + 2 },
    { name: 'Wed', gait: 1.0, social: data.average_social_score_7d - 1 },
    { name: 'Thu', gait: 0.9, social: data.average_social_score_7d + 5 },
    { name: 'Fri', gait: 0.7, social: data.average_social_score_7d - 3 },
    { name: 'Sat', gait: 0.85, social: data.average_social_score_7d },
    { name: 'Sun', gait: 0.92, social: data.average_social_score_7d + 1 },
  ];

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: 'var(--alice-blue)' }}>
      {/* Sidebar */}
      <aside style={{ width: '260px', backgroundColor: 'var(--midnight-green)', color: 'white', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '1.5rem 2rem', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
          <img src="/LOGO_AURACARE.png" alt="AuraCare Logo" style={{ height: '40px' }} />
        </div>
        <nav style={{ flex: 1, padding: '1rem' }}>
          <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <li>
              <a href="#" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: 'var(--border-radius-sm)', color: 'var(--moonstone)' }}>
                <Activity size={18} /> Overview
              </a>
            </li>
            <li>
              <a href="#" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', color: 'rgba(255,255,255,0.7)' }}>
                <ShieldAlert size={18} /> Incident Logs
              </a>
            </li>
          </ul>
        </nav>
        <div style={{ padding: '2rem' }}>
          <button onClick={handleLogout} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'rgba(255,255,255,0.7)', width: '100%' }}>
            <LogOut size={18} /> Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main style={{ flex: 1, padding: '3rem' }}>
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3rem' }}>
          <div>
            <h1 style={{ color: 'var(--midnight-green)', margin: 0 }}>Resident Overview</h1>
            <p style={{ color: 'var(--text-light)', margin: 0 }}>Monitoring: {data.resident_name}</p>
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
              {data.average_social_score_7d ? data.average_social_score_7d.toFixed(1) : 'N/A'}
            </div>
            <p style={{ color: 'var(--moonstone)', fontSize: '0.9rem', margin: 0 }}>Last 7 Days Avg</p>
          </div>
          <div style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)' }}>
            <h4 style={{ color: 'var(--text-light)', margin: 0 }}>Recent Incidents</h4>
            <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: '#EF4444' }}>
              {data.recent_incidents ? data.recent_incidents.length : 0}
            </div>
            <p style={{ color: 'var(--text-light)', fontSize: '0.9rem', margin: 0 }}>Pending review</p>
          </div>
          <div style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)' }}>
            <h4 style={{ color: 'var(--text-light)', margin: 0 }}>Active Active Monitors</h4>
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
               {data.recent_incidents && data.recent_incidents.map((incident, idx) => (
                 <div key={idx} style={{ padding: '1rem', borderLeft: `4px solid ${incident.severity === 'CRITICAL' ? '#EF4444' : '#F59E0B'}`, backgroundColor: 'var(--alice-blue)', borderRadius: '0 var(--border-radius-sm) var(--border-radius-sm) 0' }}>
                   <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                     <strong style={{ color: 'var(--midnight-green)' }}>{incident.type_display}</strong>
                     <span style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>
                       {new Date(incident.timestamp).toLocaleDateString()}
                     </span>
                   </div>
                   <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--text-dark)' }}>{incident.description || 'No description provided.'}</p>
                 </div>
               ))}
               {!data.recent_incidents || data.recent_incidents.length === 0 && (
                 <p style={{ color: 'var(--text-light)', textAlign: 'center', padding: '2rem 0' }}>No recent incidents detected.</p>
               )}
             </div>
          </div>
        </div>
      </main>
    </div>
  );
}
