import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import Login from './pages/Login';
import Signup from './pages/Signup';
import Dashboard from './pages/Dashboard';

import GaitHistory from './pages/GaitHistory';
import UploadVideo from './pages/UploadVideo';

import './index.css';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/dashboard" element={<Dashboard />} />
        
        <Route path="/gait-history" element={<GaitHistory />} />
        <Route path="/upload-video" element={<UploadVideo />} />

      </Routes>
    </Router>
  );
}

export default App;