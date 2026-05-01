export default function Footer() {
  return (
    <footer className="footer">
      <div className="container">
        <div className="footer-grid">
          <div className="footer-col">
            <h4>AuraCare</h4>
            <p>Privacy-first AI elderly care monitoring system designed to give families peace of mind and caregivers actionable insights.</p>
          </div>
          <div className="footer-col">
            <h4>Quick Links</h4>
            <ul>
              <li><a href="#about">About Us</a></li>
              <li><a href="#services">AI Modules</a></li>
              <li><a href="#process">How It Works</a></li>
              <li><a href="/login">Caregiver Login</a></li>
            </ul>
          </div>
          <div className="footer-col">
            <h4>Support</h4>
            <ul>
              <li><a href="#">Help Center</a></li>
              <li><a href="#">Privacy Policy</a></li>
              <li><a href="#">Terms of Service</a></li>
              <li><a href="#">Contact Us</a></li>
            </ul>
          </div>
        </div>
        <div className="footer-bottom">
          <p>&copy; {new Date().getFullYear()} AuraCare Analytics. All Rights Reserved.</p>
        </div>
      </div>
    </footer>
  );
}
