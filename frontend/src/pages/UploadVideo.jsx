import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { LogOut, Users, ShieldAlert, Activity, Upload, CheckCircle, AlertCircle, Video } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000/api';

export default function UploadVideo() {
  const navigate   = useNavigate();
  const token      = localStorage.getItem('access_token');
  const [file, setFile]       = useState(null);
  const [status, setStatus]   = useState('idle'); // idle, uploading, success, error
  const [message, setMessage] = useState('');
  const [dragOver, setDragOver] = useState(false);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    navigate('/login');
  };

  const handleFile = (f) => {
    if (f && f.type.startsWith('video/')) {
      setFile(f);
      setStatus('idle');
      setMessage('');
    } else {
      setMessage('Please select a valid video file (mp4, avi, mov...)');
      setStatus('error');
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    handleFile(f);
  };

  const handleSubmit = async () => {
    if (!file) return;
    setStatus('uploading');
    setMessage('Uploading and starting analysis...');

    const formData = new FormData();
    formData.append('video', file);

    try {
      const res = await axios.post(`${API_BASE}/gait/analyze/`, formData, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data',
        },
      });
      setStatus('success');
      setMessage(res.data.message);
    } catch (err) {
      setStatus('error');
      setMessage(err.response?.data?.error || 'Upload failed. Please try again.');
    }
  };

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
              <Link to="/gait-history" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', color: 'rgba(255,255,255,0.7)', textDecoration: 'none' }}>
                <Activity size={18} /> Gait History
              </Link>
            </li>
            <li>
              <Link to="/upload-video" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: 'var(--border-radius-sm)', color: 'var(--moonstone)', textDecoration: 'none' }}>
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
          <button onClick={handleLogout} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'rgba(255,255,255,0.7)', width: '100%', background: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem' }}>
            <LogOut size={18} /> Sign Out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main style={{ flex: 1, padding: '3rem' }}>
        <header style={{ marginBottom: '3rem' }}>
          <h1 style={{ color: 'var(--midnight-green)', margin: 0 }}>Upload Daily Recording</h1>
          <p style={{ color: 'var(--text-light)', margin: 0 }}>Upload corridor camera recordings for automatic gait analysis</p>
        </header>

        {/* How it works */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1.5rem', marginBottom: '3rem' }}>
          {[
            { step: '1', icon: '📹', title: 'Upload Video', desc: 'Upload the daily corridor recording from the camera' },
            { step: '2', icon: '🤖', title: 'AI Analysis', desc: 'System automatically detects and analyzes each resident\'s gait' },
            { step: '3', icon: '📊', title: 'View Results', desc: 'Check Gait History for results and alerts' },
          ].map(item => (
            <div key={item.step} style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)', textAlign: 'center' }}>
              <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>{item.icon}</div>
              <h3 style={{ color: 'var(--midnight-green)', margin: '0 0 0.5rem 0', fontSize: '1rem' }}>Step {item.step}: {item.title}</h3>
              <p style={{ color: 'var(--text-light)', margin: 0, fontSize: '0.85rem' }}>{item.desc}</p>
            </div>
          ))}
        </div>

        {/* Upload Area */}
        <div style={{ backgroundColor: 'white', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)', padding: '2rem' }}>
          <h3 style={{ color: 'var(--midnight-green)', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Video size={20} /> Select Video File
          </h3>

          {/* Drag & Drop Zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => document.getElementById('video-input').click()}
            style={{
              border: `2px dashed ${dragOver ? 'var(--moonstone)' : '#CBD5E1'}`,
              borderRadius: 'var(--border-radius)',
              padding: '3rem',
              textAlign: 'center',
              cursor: 'pointer',
              backgroundColor: dragOver ? '#F0FDFA' : '#F8FAFC',
              transition: 'all 0.2s',
              marginBottom: '1.5rem',
            }}
          >
            <input
              id="video-input"
              type="file"
              accept="video/*"
              style={{ display: 'none' }}
              onChange={(e) => handleFile(e.target.files[0])}
            />
            <Upload size={40} color={dragOver ? 'var(--moonstone)' : '#94A3B8'} style={{ marginBottom: '1rem' }} />
            {file ? (
              <div>
                <p style={{ color: 'var(--midnight-green)', fontWeight: 'bold', margin: 0 }}>✅ {file.name}</p>
                <p style={{ color: 'var(--text-light)', fontSize: '0.85rem', margin: '0.5rem 0 0 0' }}>
                  {(file.size / 1024 / 1024).toFixed(1)} MB
                </p>
              </div>
            ) : (
              <div>
                <p style={{ color: 'var(--midnight-green)', fontWeight: 'bold', margin: 0 }}>
                  Drag & drop video here or click to browse
                </p>
                <p style={{ color: 'var(--text-light)', fontSize: '0.85rem', margin: '0.5rem 0 0 0' }}>
                  Supported formats: MP4, AVI, MOV
                </p>
              </div>
            )}
          </div>

          {/* Status message */}
          {message && (
            <div style={{
              padding: '1rem',
              borderRadius: '8px',
              marginBottom: '1rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              backgroundColor: status === 'success' ? '#D1FAE5' : status === 'error' ? '#FEE2E2' : '#E0F2FE',
              color: status === 'success' ? '#065F46' : status === 'error' ? '#B91C1C' : '#0369A1',
            }}>
              {status === 'success' ? <CheckCircle size={18} /> : <AlertCircle size={18} />}
              {message}
            </div>
          )}

          {/* Buttons */}
          <div style={{ display: 'flex', gap: '1rem' }}>
            <button
              onClick={handleSubmit}
              disabled={!file || status === 'uploading'}
              style={{
                padding: '12px 32px',
                backgroundColor: !file || status === 'uploading' ? '#CBD5E1' : 'var(--midnight-green)',
                color: 'white',
                border: 'none',
                borderRadius: 'var(--border-radius-sm)',
                cursor: !file || status === 'uploading' ? 'not-allowed' : 'pointer',
                fontWeight: 'bold',
                fontSize: '1rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              {status === 'uploading' ? '⏳ Analyzing...' : '🚀 Start Analysis'}
            </button>

            {status === 'success' && (
              <button
                onClick={() => navigate('/gait-history')}
                style={{
                  padding: '12px 32px',
                  backgroundColor: 'var(--moonstone)',
                  color: 'white',
                  border: 'none',
                  borderRadius: 'var(--border-radius-sm)',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                  fontSize: '1rem',
                }}
              >
                📊 View Results
              </button>
            )}

            {file && status !== 'uploading' && (
              <button
                onClick={() => { setFile(null); setStatus('idle'); setMessage(''); }}
                style={{
                  padding: '12px 32px',
                  backgroundColor: 'white',
                  color: 'var(--text-light)',
                  border: '1px solid #CBD5E1',
                  borderRadius: 'var(--border-radius-sm)',
                  cursor: 'pointer',
                  fontSize: '1rem',
                }}
              >
                Clear
              </button>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
