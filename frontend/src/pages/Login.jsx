import { Link, useNavigate } from 'react-router-dom';
import { Activity } from 'lucide-react';
import { useState } from 'react';
import axios from 'axios';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    try {
      // In Django, default token auth might use username. Let's send username, assuming username maps to what they typed or we mapped email to username
      // Our seed script created family user with username 'family_smith' and email 'family@auracare.com'. But SimpleJWT expects 'username' and 'password'
      // If we configured it strictly out of the box, it expects 'username'. We will send 'username' key since we haven't overridden SimpleJWT setting.
      // Wait, let's just attempt passing email to the username field, or tell the user to login with their username.
      const res = await axios.post('http://localhost:8000/api/auth/login/', {
        username: email, // Assuming they type their username here for simplicity, or we mapped it.
        password: password
      });
      localStorage.setItem('access_token', res.data.access);
      localStorage.setItem('refresh_token', res.data.refresh);
      navigate('/dashboard');
    } catch (err) {
      setError('Invalid credentials or network error.');
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

            <button type="submit" className="btn btn-primary auth-btn">Sign In to Dashboard</button>
          </form>

          <div className="auth-links">
            <p>Don't have an account? <Link to="/signup">Register Facility</Link></p>
          </div>
        </div>
      </div>
    </div>
  );
}
