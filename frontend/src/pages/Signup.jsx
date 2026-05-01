import { Link, useNavigate } from 'react-router-dom';
import { ShieldCheck } from 'lucide-react';
import { useState } from 'react';
import axios from 'axios';

export default function Signup() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('family');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSignup = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    
    try {
      // Split name into first and last name loosely
      const nameParts = name.trim().split(' ');
      const firstName = nameParts[0] || '';
      const lastName = nameParts.slice(1).join(' ') || '';
      
      const payload = {
        username: email, // Using email as username for simpler login
        email: email,
        password: password,
        role: role.toUpperCase(), // backend uses uppercase choices FAMILY/CAREGIVER
        first_name: firstName,
        last_name: lastName,
      };

      await axios.post('http://127.0.0.1:8000/api/auth/register/', payload);
      navigate('/login');
    } catch (err) {
      if (err.response && err.response.data) {
        const errorData = err.response.data;
        // Join the errors nicely or pick the first
        const firstErrorKey = Object.keys(errorData)[0];
        if (firstErrorKey) {
          setError(`${firstErrorKey}: ${errorData[firstErrorKey]}`);
        } else {
          setError('Failed to register. Please check your inputs.');
        }
      } else {
        setError('Network error or server is unavailable.');
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
          <ShieldCheck size={64} color="var(--moonstone)" style={{ marginBottom: '1rem' }} />
          <h2>Join AuraCare</h2>
          <p>Register your facility or family account to start receiving vital AI telemetry alerts today.</p>
        </div>
      </div>
      
      <div className="auth-panel">
        <div className="auth-form-container">
          <h3>Create an Account</h3>
          <p className="subtitle">Securely connect to your nursing home facility.</p>
          
          {error && <div style={{ color: '#EF4444', marginBottom: '1rem', textAlign: 'center', fontWeight: 'bold' }}>{error}</div>}
          
          <form onSubmit={handleSignup}>
            <div className="form-group">
              <label htmlFor="name">Full Name</label>
              <input type="text" id="name" placeholder="John Doe" value={name} onChange={e => setName(e.target.value)} required />
            </div>

            <div className="form-group">
              <label htmlFor="email">Email Address</label>
              <input type="email" id="email" placeholder="john@example.com" value={email} onChange={e => setEmail(e.target.value)} required />
            </div>

            <div className="form-group" style={{ display: 'flex', gap: '1rem' }}>
                <div style={{ flex: 1 }}>
                    <label htmlFor="password">Password</label>
                    <input type="password" id="password" placeholder="••••••••" value={password} onChange={e => setPassword(e.target.value)} required minLength={8} />
                </div>
                <div style={{ flex: 1 }}>
                    <label htmlFor="role">Role</label>
                    <select id="role" style={{ width: '100%', padding: '12px 16px', border: '2px solid var(--timberwolf)', borderRadius: 'var(--border-radius-sm)', backgroundColor: 'white', outline: 'none' }} value={role} onChange={e => setRole(e.target.value)}>
                        <option value="family">Family Member</option>
                        <option value="caregiver">Caregiver</option>
                    </select>
                </div>
            </div>

            <button type="submit" className="btn btn-primary auth-btn" style={{ marginTop: '1.5rem' }} disabled={loading}>
              {loading ? 'Registering...' : 'Register Account'}
            </button>
          </form>

          <div className="auth-links">
            <p>Already have an account? <Link to="/login">Sign In</Link></p>
          </div>
        </div>
      </div>
    </div>
  );
}
