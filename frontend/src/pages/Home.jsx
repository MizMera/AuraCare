import { ShieldAlert, Footprints, Ear, UserMinus, Activity, BellRing } from 'lucide-react';
import Header from '../components/Header';
import Footer from '../components/Footer';
import { Link } from 'react-router-dom';

export default function Home() {
  return (
    <>
      <Header />
      <main>
        {/* HERO SECTION */}
        <section className="hero">
          <div className="container">
            <div className="hero-content">
              <h1>Privacy-First AI Elderly Monitoring</h1>
              <p>
                AuraCare provides 24/7 intelligent observation without invading personal privacy. 
                Our AI modules analyze movements and behavior to instantly alert you when emergencies occur.
              </p>
              <div style={{ display: 'flex', gap: '1rem' }}>
                <Link to="/login" className="btn btn-primary">Dashboard Login</Link>
                <a href="#about" className="btn btn-secondary">Learn More</a>
              </div>
            </div>
            <div className="hero-image">
              <img src="/Senior-and-Elderly-Care-Living-Options.jpg" alt="Caring nurse with elderly patient" style={{ width: '100%', borderRadius: 'var(--border-radius-lg)', boxShadow: 'var(--box-shadow)' }}/>
              <div className="status-card">
                <div className="status-icon">
                  <Activity size={24} />
                </div>
                <div>
                  <h4 style={{ color: 'var(--midnight-green)', marginBottom: '0.2rem' }}>System Status</h4>
                  <p style={{ color: 'var(--text-light)', fontSize: '0.9rem', margin: 0 }}>7 AI Modules Active 24/7</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ABOUT US SPLIT */}
        <section id="about" className="about">
          <div className="container">
            <div className="about-image">
              <img src="/nurselaughingresident.jpg" alt="Caring nurse laughing with resident" />
            </div>
            <div className="about-content">
              <span className="section-label">About AuraCare</span>
              <h2 className="section-title">Our Practice: Excellent Care,<br/>Humane Principles</h2>
              <p style={{ color: 'var(--text-light)', fontSize: '1.1rem', marginBottom: '1.5rem' }}>
                We believe that safety shouldn't come at the cost of dignity. By leveraging advanced edge-AI, 
                secure telemetry data ingestion, and actionable dashboard interfaces, AuraCare turns visual and audio feeds 
                into actionable numbers without ever storing raw footage.
              </p>
              <ul style={{ display: 'flex', flexDirection: 'column', gap: '1rem', color: 'var(--midnight-green)', fontWeight: '500' }}>
                <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Activity color="var(--moonstone)" size={20}/> Privacy-Compliant Monitoring</li>
                <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><BellRing color="var(--moonstone)" size={20}/> Instant Emergency Alerts</li>
                <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><ShieldAlert color="var(--moonstone)" size={20}/> Dedicated Family & Caregiver Views</li>
              </ul>
            </div>
          </div>
        </section>

        {/* PROCESS / HOW IT WORKS */}
        <section id="process" className="process">
          <div className="container">
            <span className="section-label" style={{ color: 'white' }}>How It Works</span>
            <h2 className="section-title">Simplified 3-Step Process</h2>
            
            <div className="process-grid">
              <div className="process-step">
                <div className="process-number">01</div>
                <h3>Devices Detect</h3>
                <p style={{ color: 'var(--timberwolf)', marginTop: '0.5rem' }}>
                  Microphones and cameras in public zones feed live stream data directly to local edge nodes.
                </p>
              </div>
              <div className="process-step">
                <div className="process-number">02</div>
                <h3>AI Analyzes</h3>
                <p style={{ color: 'var(--timberwolf)', marginTop: '0.5rem' }}>
                  Our AI models translate raw feeds into secure Health Metrics and Incident logs seamlessly.
                </p>
              </div>
              <div className="process-step">
                <div className="process-number">03</div>
                <h3>Action Taken</h3>
                <p style={{ color: 'var(--timberwolf)', marginTop: '0.5rem' }}>
                  Critical events trigger immediate dashboard notifications and alerts for caregivers and family members.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* AI MODULES / SERVICES */}
        <section id="services" className="services">
          <div className="container">
            <span className="section-label">AuraCare AI Modules</span>
            <h2 className="section-title">Comprehensive Protection</h2>
            
            <div className="services-grid">
              <div className="service-card">
                <div className="service-icon"><ShieldAlert size={32} /></div>
                <h3 style={{ color: 'var(--midnight-green)', marginBottom: '0.5rem' }}>Fall Detection</h3>
                <p style={{ color: 'var(--text-light)', fontSize: '0.9rem' }}>Real-time posture analysis detects falls and immediately flags them as Critical incidents.</p>
              </div>
              
              <div className="service-card">
                <div className="service-icon"><Footprints size={32} /></div>
                <h3 style={{ color: 'var(--midnight-green)', marginBottom: '0.5rem' }}>Wandering Prevention</h3>
                <p style={{ color: 'var(--text-light)', fontSize: '0.9rem' }}>Tracks movement patterns to ensure residents stay within designated safe zones.</p>
              </div>

              <div className="service-card">
                <div className="service-icon"><UserMinus size={32} /></div>
                <h3 style={{ color: 'var(--midnight-green)', marginBottom: '0.5rem' }}>Absence Detection</h3>
                <p style={{ color: 'var(--text-light)', fontSize: '0.9rem' }}>Cross-references physical location with scheduling to alert for missing persons.</p>
              </div>

              <div className="service-card">
                <div className="service-icon"><Ear size={32} /></div>
                <h3 style={{ color: 'var(--midnight-green)', marginBottom: '0.5rem' }}>Distress & Audio</h3>
                <p style={{ color: 'var(--text-light)', fontSize: '0.9rem' }}>YAMNet models detect distress cries or vocal expressions of aggression safely.</p>
              </div>
              
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
