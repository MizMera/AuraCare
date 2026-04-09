import { Link } from 'react-router-dom';
import { Activity, ShieldCheck } from 'lucide-react';

export default function Signup() {
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
          
          <form onSubmit={(e) => e.preventDefault()}>
            <div className="form-group">
              <label htmlFor="name">Full Name</label>
              <input type="text" id="name" placeholder="John Doe" />
            </div>

            <div className="form-group">
              <label htmlFor="email">Email Address</label>
              <input type="email" id="email" placeholder="john@example.com" />
            </div>

            <div className="form-group" style={{ display: 'flex', gap: '1rem' }}>
                <div style={{ flex: 1 }}>
                    <label htmlFor="password">Password</label>
                    <input type="password" id="password" placeholder="••••••••" />
                </div>
                <div style={{ flex: 1 }}>
                    <label htmlFor="role">Role</label>
                    <select id="role" style={{ width: '100%', padding: '12px 16px', border: '2px solid var(--timberwolf)', borderRadius: 'var(--border-radius-sm)', backgroundColor: 'white', outline: 'none' }}>
                        <option value="family">Family Member</option>
                        <option value="caregiver">Caregiver</option>
                    </select>
                </div>
            </div>

            <button type="submit" className="btn btn-primary auth-btn" style={{ marginTop: '1.5rem' }}>Register Account</button>
          </form>

          <div className="auth-links">
            <p>Already have an account? <Link to="/login">Sign In</Link></p>
          </div>
        </div>
      </div>
    </div>
  );
}
