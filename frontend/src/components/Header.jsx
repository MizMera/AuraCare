import { Link } from 'react-router-dom';
import { Activity } from 'lucide-react';

export default function Header() {
  return (
    <header className="header">
      <div className="container header-container">
        <Link to="/" className="logo">
          <img src="/LOGO_AURACARE.png" alt="AuraCare Logo" style={{ height: '40px' }} />
        </Link>
        <nav className="nav-links">
          <Link to="/">Home</Link>
          <a href="#about">About</a>
          <a href="#services">AI Modules</a>
          <a href="#process">How It Works</a>
        </nav>
        <div className="header-actions" style={{ display: 'flex', gap: '0.85rem', alignItems: 'center' }}>
          <Link to="/family-portal" className="btn header-top-btn header-top-btn-secondary">Family Portal</Link>
          <Link to="/login" className="btn header-top-btn header-top-btn-primary">Dashboard Login</Link>
        </div>
      </div>
    </header>
  );
}
