import { Link, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import axios from 'axios';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await axios.post('http://127.0.0.1:8000/api/auth/login/', {
        username: email, // Backend EmailBackend allows finding user by email
        password: password
      });
      localStorage.setItem('access_token', res.data.access);
      localStorage.setItem('refresh_token', res.data.refresh);
      navigate('/dashboard');
    } catch (err) {
      if (err.response && err.response.data && err.response.data.detail) {
        setError(err.response.data.detail);
      } else {
        setError('Invalid credentials or network error.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-visual">
        <Link to="/" style={{ position: 'absolute', top: '2rem', left: '2rem' }}>
          <img src="/LOGO_AURACARE.png" alt="AuraCare Logo" style={{ height: '50px' }} />
        </Link>
        <div style={{ marginTop: 'auto', marginBottom: 'auto' }}>
          <h2>Welcome Back</h2>
          <p>Sign in to your dashboard to monitor resident status, view AI detections, and manage operations.</p>
        </div>
      </div>
      
      <div className="auth-panel">
        <div className="auth-form-container">
          <h3>Log In</h3>
          <p className="subtitle">Enter your registered email address or contact admin.</p>
          
          {error && <div style={{ color: '#EF4444', marginBottom: '1rem', textAlign: 'center', fontWeight: 'bold' }}>{error}</div>}
          
          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label htmlFor="email">Email Address</label>
              <input type="text" id="email" placeholder="family@auracare.com" value={email} onChange={e => setEmail(e.target.value)} required />
            </div>
            
            <div className="form-group">
              <label htmlFor="password">Password</label>
              <input type="password" id="password" placeholder="••••••••" value={password} onChange={e => setPassword(e.target.value)} required />
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1.5rem' }}>
              <a href="#" style={{ color: 'var(--moonstone)', fontSize: '0.9rem' }}>Forgot password?</a>
            </div>

            <button type="submit" className="btn btn-primary auth-btn" disabled={loading}>
              {loading ? 'Signing In...' : 'Sign In to Dashboard'}
            </button>
          </form>

          <div className="auth-links">
            <p>Don't have an account? <Link to="/signup">Register Facility</Link></p>
          </div>
        </div>
      </div>
    </div>
  );
}
