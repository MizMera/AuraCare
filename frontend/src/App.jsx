import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import Login from './pages/Login';
import Signup from './pages/Signup';
import Dashboard from './pages/Dashboard';
import MonitoringDashboard from './pages/MonitoringDashboard';
import './index.css';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/monitoring" element={<MonitoringDashboard />} />
        <Route path="/monitoring/log-activities" element={<MonitoringDashboard />} />
        <Route path="/monitoring/log-activities/resident-entry" element={<MonitoringDashboard />} />
        <Route path="/monitoring/log-activities/camera-detection" element={<MonitoringDashboard />} />
        <Route path="/monitoring/log-activities/summary-generation" element={<MonitoringDashboard />} />
      </Routes>
    </Router>
  );
}

export default App;
