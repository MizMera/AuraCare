import { useEffect, useRef, useState } from 'react';
import { Navigate, useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import {
  LogOut, Activity, AlertCircle, ShieldAlert, Users, Video,
  Eye, Brain, UtensilsCrossed, Clock3, Plus, Pencil, Trash2, CheckCircle2, Sparkles, Pill,
  Camera, FileText,
} from 'lucide-react';
import SocialInteraction from './SocialInteraction';
import WanderingDetection from './WanderingDetection';
import ResidentsPage from './ResidentsPage';
import DiabetesMonitor from './DiabetesMonitor';
import NotificationBell from '../components/NotificationBell';
import GaitAnalysisPanel from '../components/GaitAnalysisPanel';
import ChatbotWidget from '../components/ChatbotWidget';
import { mealService } from '../services/mealService';
import MedicationPanel from '../components/MedicationPanel';
import MealAttendance from './MealAttendance';
import { VoiceRecorder, ReportsDashboard } from '../components/ShiftHandover';
import ShiftManagement from '../components/Admin/ShiftManagement';
const API_HOST = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';
const API_BASE = `http://${API_HOST}:8000/api`;

const navBtn = (active) => ({
  display: 'flex',
  alignItems: 'center',
  gap: '0.5rem',
  padding: '10px 15px',
  width: '100%',
  textAlign: 'left',
  border: 'none',
  cursor: 'pointer',
  fontSize: 14,
  background: 'none',
  borderRadius: 'var(--border-radius-sm)',
  backgroundColor: active ? 'rgba(255,255,255,0.15)' : 'transparent',
  color: active ? 'var(--moonstone)' : 'rgba(255,255,255,0.7)',
  fontWeight: active ? 700 : 400,
  transition: 'transform 0.18s ease, background-color 0.18s ease, color 0.18s ease',
});
const sidebarBtnHoverHandlers = {
  onMouseEnter: (event) => {
    event.currentTarget.style.transform = 'translateX(2px)';
    if (event.currentTarget.style.backgroundColor === 'transparent') {
      event.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.08)';
    }
  },
  onMouseLeave: (event) => {
    event.currentTarget.style.transform = 'translateX(0)';
    if (event.currentTarget.style.fontWeight !== '700') {
      event.currentTarget.style.backgroundColor = 'transparent';
    }
  },
};

const INCIDENT_COLORS = {
  FALL: { bg: '#FEE2E2', border: '#DC2626', text: '#7F1D1D', badge: '#EF4444' },
  FALL_RISK: { bg: '#FFFBEB', border: '#D97706', text: '#78350F', badge: '#F59E0B' },
  AGGRESSION: { bg: '#FFF7ED', border: '#EA580C', text: '#7C2D12', badge: '#F97316' },
  WANDERING: { bg: '#FEF3C7', border: '#D97706', text: '#78350F', badge: '#F59E0B' },
  DISTRESS_CRY: { bg: '#EDE9FE', border: '#7C3AED', text: '#4C1D95', badge: '#8B5CF6' },
  CARDIAC: { bg: '#FCE7F3', border: '#DB2777', text: '#831843', badge: '#EC4899' },
  ABSENCE: { bg: '#E0F2FE', border: '#0284C7', text: '#0C4A6E', badge: '#0EA5E9' },
};

const DEFAULT_COLOR = { bg: '#FEE2E2', border: '#DC2626', text: '#7F1D1D', badge: '#EF4444' };
const sectionCardStyle = {
  backgroundColor: 'white',
  padding: '1.5rem',
  borderRadius: 'var(--border-radius)',
  boxShadow: 'var(--box-shadow)',
};
const formInputStyle = {
  width: '100%',
  border: '1px solid #D7E3EA',
  borderRadius: '12px',
  padding: '12px 14px',
  fontSize: '0.95rem',
  color: 'var(--midnight-green)',
  backgroundColor: '#F9FCFE',
  boxSizing: 'border-box',
};
const formLabelStyle = {
  display: 'block',
  fontSize: '0.82rem',
  fontWeight: 700,
  color: 'var(--midnight-green)',
  marginBottom: '0.45rem',
};
const logoutDockStyle = {
  position: 'sticky',
  bottom: '1rem',
  margin: '1rem',
  padding: 0,
  borderRadius: 0,
  backgroundColor: 'transparent',
  backdropFilter: 'none',
};
const logoutBtnStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '0.5rem',
  color: 'white',
  width: '100%',
  background: 'rgba(255,255,255,0.06)',
  border: '1px solid rgba(255,255,255,0.22)',
  borderRadius: '12px',
  padding: '0.7rem 0.9rem',
  cursor: 'pointer',
  fontSize: '0.95rem',
  fontWeight: 700,
  transition: 'transform 0.18s ease, background-color 0.18s ease',
};
const logTabBtnStyle = (active) => ({
  display: 'flex',
  alignItems: 'center',
  gap: '0.45rem',
  padding: '0.7rem 1rem',
  borderRadius: '12px',
  border: `1px solid ${active ? 'var(--moonstone)' : '#D7E3EA'}`,
  backgroundColor: active ? '#EAF7FA' : 'white',
  color: active ? 'var(--midnight-green)' : 'var(--text-light)',
  fontWeight: active ? 700 : 600,
  fontSize: '0.92rem',
  cursor: 'pointer',
  transition: 'all 0.18s ease',
});
const logAlertStyle = (tone) => ({
  padding: '0.9rem 1rem',
  borderRadius: '12px',
  border: tone === 'error' ? '1px solid #F5C2C7' : '1px solid #BFE7DB',
  backgroundColor: tone === 'error' ? '#FEF2F2' : '#F0FDFA',
  color: tone === 'error' ? '#B91C1C' : 'var(--midnight-green)',
  boxShadow: 'var(--box-shadow)',
});
const logInfoTileStyle = {
  padding: '1rem',
  backgroundColor: '#F9FCFE',
  borderRadius: '12px',
  border: '1px solid #D7E3EA',
};
const logInsetPanelStyle = {
  padding: '1rem',
  backgroundColor: '#F9FCFE',
  borderRadius: '14px',
  border: '1px solid #D7E3EA',
};

function getIncidentColor(type) {
  return INCIDENT_COLORS[type] || DEFAULT_COLOR;
}



/* ── Log-Activities helpers ──────────────────────────────────────── */
function formatTimestamp(value) {
  if (!value) return 'No recent signal';
  const ms = typeof value === 'number' ? value * 1000 : Date.parse(value);
  if (Number.isNaN(ms)) return 'No recent signal';
  return new Date(ms).toLocaleString();
}

function formatDurationWords(seconds) {
  const s = Math.max(0, Math.round(seconds));
  if (s === 0) return '0 seconds';
  if (s < 60) return `${s} second${s !== 1 ? 's' : ''}`;
  const m = Math.round(s / 60);
  return `${m} minute${m !== 1 ? 's' : ''}`;
}

function formatHistoryEntry(entry) {
  const name = entry.name || 'Unknown';
  const location = entry.location || 'Unknown location';
  const rawText = entry.summary_text || '';
  const bracketMatch = rawText.match(/\[([^\]]+)\]/);
  if (bracketMatch) {
    const parts = {};
    bracketMatch[1].split(',').forEach((p) => {
      const [act, val] = p.split('=');
      if (act && val) parts[act.trim()] = parseFloat(val);
    });
    const standing = parts.standing || 0;
    const sitting = parts.sitting || 0;
    const walking = parts.walking || 0;
    const total = standing + sitting + walking;
    return (
      `${name} was detected in ${location} for ${formatDurationWords(total)}. ` +
      `Standing: ${formatDurationWords(standing)}, Sitting: ${formatDurationWords(sitting)}, Walking: ${formatDurationWords(walking)}.`
    );
  }
  return rawText.replace(/\[.*?\]/g, '').trim() || 'No summary available.';
}

function getCameraSourceType(source) {
  if (!source) return 'none';
  const s = String(source).trim().toLowerCase();
  if (s.startsWith('rtsp://')) return 'rtsp';
  if (s.endsWith('.m3u8') || s.includes('.m3u8?')) return 'hls';
  if (s.endsWith('.mp4') || s.includes('.mp4?')) return 'video';
  if (s.endsWith('.mjpg') || s.endsWith('.mjpeg') || s.includes('/mjpg') || s.includes('/mjpeg')) return 'mjpeg';
  if (s.startsWith('http://') || s.startsWith('https://')) return 'web';
  return 'unknown';
}

function EmptyLogPanel({ title, message }) {
  return (
    <div style={{ textAlign: 'center', padding: '2rem', backgroundColor: 'var(--alice-blue)', borderRadius: '12px' }}>
      <h3 style={{ color: 'var(--midnight-green)', marginTop: 0, marginBottom: '0.5rem' }}>{title}</h3>
      <p style={{ color: 'var(--text-light)', margin: 0 }}>{message}</p>
    </div>
  );
}
/* ─────────────────────────────────────────────────────────────────── */

function StaffDashboard({ token, onLogout, role }) {
  const [facilityIncidents, setFacilityIncidents] = useState([]);
  const [staffSection, setStaffSection] = useState('residents-db');
  const [loading, setLoading] = useState(true);
  const [streamRunning, setStreamRunning] = useState(false);
  const [streamLoading, setStreamLoading] = useState(false);
  const [streamError, setStreamError] = useState('');
  const [streamKey, setStreamKey] = useState(0);
  const streamPollRef = useRef(null);
  const [refreshKey, setRefreshKey] = useState(0);

  /* ── Log-Activities state ───────────────────────────────────────── */
  const [logActivitiesTab, setLogActivitiesTab] = useState('camera');
  const [busyStartingModels, setBusyStartingModels] = useState(false);
  const [busyStoppingModels, setBusyStoppingModels] = useState(false);
  const [runModelsMessage, setRunModelsMessage] = useState('');
  const [runModelsError, setRunModelsError] = useState('');
  const [generateMessage, setGenerateMessage] = useState('');
  const [logCameras, setLogCameras] = useState([]);
  const [selectedLogCameraId, setSelectedLogCameraId] = useState('');
  const [cameraDetectionPayload, setCameraDetectionPayload] = useState(null);
  const [cameraDetectionError, setCameraDetectionError] = useState('');
  const [localCameras, setLocalCameras] = useState([]);
  const [selectedLocalCameraId, setSelectedLocalCameraId] = useState('');
  const [localCameraError, setLocalCameraError] = useState('');
  const [localCameraReady, setLocalCameraReady] = useState(false);
  const [livePreviewUrl, setLivePreviewUrl] = useState('');
  const [pipelineSummary, setPipelineSummary] = useState([]);
  const [pipelineHistory, setPipelineHistory] = useState([]);
  /* ─────────────────────────────────────────────────────────────────── */
  const handleRecordingSuccess = () => {
    setRefreshKey(prev => prev + 1);
  };
  useEffect(() => {
    const fetchStaffDashboard = async () => {
      try {
        const incidentsResponse = await axios.get(`${API_BASE}/mobile/facility-incidents/`, { headers: { Authorization: `Bearer ${token}` } });
        setFacilityIncidents(incidentsResponse.data || []);
      } catch (err) {
        if (err.response?.status === 401) onLogout();
      } finally {
        setLoading(false);
      }
    };
    fetchStaffDashboard();
  }, [token, onLogout]);

  useEffect(() => () => {
    if (streamPollRef.current) {
      window.clearInterval(streamPollRef.current);
    }
  }, []);

  const API_KEY = 'default-secret-key';

  const handleStartStream = async () => {
    setStreamLoading(true);
    setStreamError('');
    try {
      const response = await axios.post(
        `${API_BASE}/stream/aggression/start/`,
        { camera: 0, device_id: 'CAM_01' },
        { headers: { 'X-API-KEY': API_KEY } },
      );
      if (!response.data?.running) {
        throw new Error(response.data?.error || 'Unable to keep the aggression stream running.');
      }
      setStreamRunning(true);
      setStreamError('');
      setStreamKey((prev) => prev + 1);
    } catch (e) {
      let msg = e.response?.data?.error || e.message || 'Unknown error starting stream';
      if (e.message === 'Network Error') {
        msg = 'Network Error: Cannot connect to the local Django server on port 8000. Is it running?';
      }
      setStreamError(msg);
    } finally {
      setStreamLoading(false);
    }
  };

  const handleStopStream = async () => {
    setStreamLoading(true);
    try {
      await axios.post(`${API_BASE}/stream/aggression/stop/`, {}, { headers: { 'X-API-KEY': API_KEY } });
      if (streamPollRef.current) {
        window.clearInterval(streamPollRef.current);
        streamPollRef.current = null;
      }
      setStreamRunning(false);
      setStreamError('');
    } catch (e) {
      console.error('Failed to stop stream', e);
    } finally {
      setStreamLoading(false);
    }
  };

  useEffect(() => {
    if (!streamRunning) return undefined;

    const pollStreamStatus = async () => {
      try {
        const response = await axios.get(`${API_BASE}/stream/aggression/status/`);
        if (!response.data?.running) {
          setStreamRunning(false);
          setStreamError(
            response.data?.error
            || 'Live aggression detection stopped unexpectedly. If the meal camera is open, stop it first and try again.',
          );
          return;
        }
        if (response.data?.error) {
          setStreamError(response.data.error);
        }
      } catch {
        setStreamRunning(false);
        setStreamError('Unable to read live aggression status right now.');
      }
    };

    pollStreamStatus();
    streamPollRef.current = window.setInterval(pollStreamStatus, 1500);

    return () => {
      if (streamPollRef.current) {
        window.clearInterval(streamPollRef.current);
        streamPollRef.current = null;
      }
    };
  }, [streamRunning]);

  /* ── Log-Activities: load cameras + pipeline data ──────────────── */
  useEffect(() => {
    if (staffSection !== 'logActivities') return;
    let cancelled = false;
    const load = async () => {
      try {
        const [camRes, sumRes, histRes] = await Promise.allSettled([
          axios.get(`${API_BASE}/monitoring/cameras/`, { headers: { Authorization: `Bearer ${token}` } }),
          axios.get(`${API_BASE}/monitoring/summary/?window_hours=24`, { headers: { Authorization: `Bearer ${token}` } }),
          axios.get(`${API_BASE}/monitoring/history/?limit=120`, { headers: { Authorization: `Bearer ${token}` } }),
        ]);
        if (cancelled) return;
        if (camRes.status === 'fulfilled') {
          const list = camRes.value.data.cameras || [];
          setLogCameras(list);
          setSelectedLogCameraId((cur) => cur || (list[0] ? String(list[0].id) : ''));
        }
        if (sumRes.status === 'fulfilled') {
          setPipelineSummary(Object.values(sumRes.value.data.summary || {}));
        }
        if (histRes.status === 'fulfilled') {
          setPipelineHistory(histRes.value.data.history || []);
        }
      } catch { /* ignore */ }
    };
    load();
    return () => { cancelled = true; };
  }, [staffSection, token]);

  /* ── Log-Activities: enumerate local PC cameras ─────────────────── */
  useEffect(() => {
    if (staffSection !== 'logActivities' || logActivitiesTab !== 'camera') return;
    const enumerate = async () => {
      if (!navigator.mediaDevices?.enumerateDevices) {
        setLocalCameraError('This browser does not support camera detection.');
        return;
      }
      try {
        // Ask for camera permission so enumerateDevices returns real labels/IDs
        let permStream = null;
        try {
          permStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        } catch { /* permission denied — enumerate anyway */ }
        const devices = await navigator.mediaDevices.enumerateDevices();
        if (permStream) permStream.getTracks().forEach((t) => t.stop());
        const video = devices.filter((d) => d.kind === 'videoinput').map((d, i) => ({
          id: d.deviceId,
          label: d.label || `PC Camera ${i + 1}`,
        }));
        // Always keep at least a placeholder so the Start button is enabled
        const final = video.length ? video : [{ id: 'default', label: 'PC Camera 1' }];
        setLocalCameras(final);
        setSelectedLocalCameraId((cur) => cur || final[0]?.id || '');
        setLocalCameraError('');
      } catch {
        // Even on error, insert a placeholder so the button stays enabled
        setLocalCameras([{ id: 'default', label: 'PC Camera 1' }]);
        setLocalCameraError('Unable to detect PC cameras — will use default camera.');
      }
    };
    enumerate();
  }, [staffSection, logActivitiesTab]);

  /* ── Log-Activities: live-preview polling ────────────────────────── */
  useEffect(() => {
    if (staffSection !== 'logActivities' || logActivitiesTab !== 'camera') {
      setLivePreviewUrl((u) => { if (u) URL.revokeObjectURL(u); return ''; });
      return;
    }
    let cancelled = false;
    let timerId = null;
    const fetchFrame = async () => {
      try {
        const res = await axios.get(`${API_BASE}/monitoring/live-preview/`, {
          headers: { Authorization: `Bearer ${token}` },
          responseType: 'blob',
        });
        if (cancelled) return;
        const next = URL.createObjectURL(res.data);
        setLivePreviewUrl((cur) => { if (cur) URL.revokeObjectURL(cur); return next; });
        setLocalCameraReady(true);
      } catch (err) {
        if (err.response?.status === 401) { onLogout(); return; }
      } finally {
        if (!cancelled) timerId = setTimeout(fetchFrame, 350);
      }
    };
    fetchFrame();
    return () => {
      cancelled = true;
      if (timerId) clearTimeout(timerId);
      setLivePreviewUrl((u) => { if (u) URL.revokeObjectURL(u); return ''; });
    };
  }, [staffSection, logActivitiesTab, token, onLogout]);

  /* ── Log-Activities: camera-detection polling ────────────────────── */
  useEffect(() => {
    if (!selectedLogCameraId) { setCameraDetectionPayload(null); return; }
    let cancelled = false;
    const fetch_ = async () => {
      try {
        const res = await axios.get(`${API_BASE}/monitoring/cameras/${selectedLogCameraId}/detections/`, { headers: { Authorization: `Bearer ${token}` } });
        if (!cancelled) { setCameraDetectionPayload(res.data); setCameraDetectionError(''); }
      } catch (err) {
        if (err.response?.status === 401) { onLogout(); return; }
        if (!cancelled) setCameraDetectionError('Unable to fetch live camera detections right now.');
      }
    };
    fetch_();
    const id = setInterval(fetch_, 5000);
    return () => { cancelled = true; clearInterval(id); };
  }, [selectedLogCameraId, token, onLogout]);

  const handleRunModels = async () => {
    setBusyStartingModels(true);
    setRunModelsMessage('');
    setRunModelsError('');
    try {
      const realCameras = localCameras.filter((c) => c.id && c.id !== 'default');
      const idx = realCameras.findIndex((c) => c.id === selectedLocalCameraId);
      const cameraIndex = idx >= 0 ? idx : 0;
      const res = await axios.post(`${API_BASE}/monitoring/start/`, {
        available_only: false,
        pc_camera_index: cameraIndex,
      }, { headers: { Authorization: `Bearer ${token}` } });
      setRunModelsMessage(res.data?.using_machine7_models
        ? `Machine7 models started on PC camera ${idx >= 0 ? idx : 0}.`
        : 'Monitoring started (compatibility mode).');
    } catch (err) {
      if (err.response?.status === 401) { onLogout(); return; }
      setRunModelsError(err.response?.data?.error || err.response?.data?.detail || 'Unable to start models right now.');
    } finally {
      setBusyStartingModels(false);
    }
  };

  const handleStopModels = async () => {
    setBusyStoppingModels(true);
    setRunModelsMessage('');
    setRunModelsError('');
    setGenerateMessage('');
    try {
      const stopRes = await axios.post(`${API_BASE}/monitoring/stop/`, {}, { headers: { Authorization: `Bearer ${token}` } });
      setLivePreviewUrl((u) => { if (u) URL.revokeObjectURL(u); return ''; });
      setLocalCameraReady(false);
      try {
        const sumRes = await axios.get(`${API_BASE}/monitoring/generate-summary/`, { headers: { Authorization: `Bearer ${token}` } });
        const count = Number(sumRes.data?.generated_count || 0);
        setGenerateMessage(count > 0 ? `Generated ${count} summary snapshot(s).` : 'Detection stopped — no summary snapshots generated.');
        if (sumRes.status === 200) {
          const [sumData, histData] = await Promise.allSettled([
            axios.get(`${API_BASE}/monitoring/summary/?window_hours=24`, { headers: { Authorization: `Bearer ${token}` } }),
            axios.get(`${API_BASE}/monitoring/history/?limit=120`, { headers: { Authorization: `Bearer ${token}` } }),
          ]);
          if (sumData.status === 'fulfilled') setPipelineSummary(Object.values(sumData.value.data.summary || {}));
          if (histData.status === 'fulfilled') setPipelineHistory(histData.value.data.history || []);
        }
      } catch (sumErr) {
        if (sumErr.response?.status === 401) { onLogout(); return; }
        setGenerateMessage(sumErr.response?.data?.error || 'Detection stopped, but summary generation failed.');
      }
      setRunModelsMessage(stopRes.data?.stopped ? 'Detection stopped.' : 'Stop signal sent.');
    } catch (err) {
      if (err.response?.status === 401) { onLogout(); return; }
      setRunModelsError(err.response?.data?.error || err.response?.data?.detail || 'Unable to stop detection right now.');
    } finally {
      setBusyStoppingModels(false);
    }
  };

  const handleStartCameraAndModels = async () => {
    setLocalCameraError('');
    await handleRunModels();
  };
  /* ─────────────────────────────────────────────────────────────────── */

  if (loading) return <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--midnight-green)' }}><h2>Loading Staff Dashboard...</h2></div>;

  /* ── Log-Activities computed ─────────────────────────────────────── */
  const selectedLogCamera = logCameras.find((c) => String(c.id) === String(selectedLogCameraId));
  const selectedCameraSourceType = getCameraSourceType(selectedLogCamera?.source);
  const detectionModeLabel = cameraDetectionPayload?.using_machine7_models ? 'True Machine7 detection' : 'Compatibility detection';
  const detectionModeColor = cameraDetectionPayload?.using_machine7_models ? '#0F766E' : '#B45309';
  const isTrueDetectionRunning = Boolean(cameraDetectionPayload?.true_detection_running);
  /* ─────────────────────────────────────────────────────────────────── */

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: 'var(--alice-blue)' }}>
      <aside style={{ width: '260px', backgroundColor: 'var(--midnight-green)', color: 'white', display: 'flex', flexDirection: 'column', position: 'sticky', top: 0, height: '100vh', overflowY: 'auto' }}>
        <div style={{ padding: '1.5rem 2rem', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '8px', textDecoration: 'none', color: 'white', fontSize: '1.5rem', fontWeight: 'bold' }}>
            <img src="/LOGO_AURACARE.png" alt="AuraCare Logo" style={{ height: '40px' }} />
            AuraCare
          </Link>
        </div>
        <nav style={{ flex: 1, padding: '1rem' }}>
          <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', listStyle: 'none', padding: 0 }}>
            <li><button type="button" onClick={() => setStaffSection('residents-db')} style={navBtn(staffSection === 'residents-db')} {...sidebarBtnHoverHandlers}><Users size={18} /> Residents Information</button></li>
            <li><button type="button" onClick={() => setStaffSection('diabetes')} style={navBtn(staffSection === 'diabetes')} {...sidebarBtnHoverHandlers}><Activity size={18} /> Glucose Monitoring</button></li>
            <li><button type="button" onClick={() => setStaffSection('incidents')} style={navBtn(staffSection === 'incidents')} {...sidebarBtnHoverHandlers}><ShieldAlert size={18} /> Facility Incidents</button></li>
            <li><button type="button" onClick={() => setStaffSection('meals')} style={navBtn(staffSection === 'meals')} {...sidebarBtnHoverHandlers}><UtensilsCrossed size={18} /> Meals & Alerts</button></li>
            <li><button type="button" onClick={() => setStaffSection('gait')} style={navBtn(staffSection === 'gait')} {...sidebarBtnHoverHandlers}><Activity size={18} /> Gait Analysis</button></li>
            <li><button type="button" onClick={() => setStaffSection('livefeed')} style={navBtn(staffSection === 'livefeed')} {...sidebarBtnHoverHandlers}><Video size={18} /> Live Feed</button></li>
            <li><button type="button" onClick={() => setStaffSection('combi')} style={navBtn(staffSection === 'combi')} {...sidebarBtnHoverHandlers}><Brain size={18} /> Social Interaction</button></li>
            <li><button type="button" onClick={() => setStaffSection('wandering')} style={navBtn(staffSection === 'wandering')} {...sidebarBtnHoverHandlers}><Sparkles size={18} /> Wandering Detection</button></li>
            <li><button type="button" onClick={() => setStaffSection('medication')} style={navBtn(staffSection === 'medication')}><Pill size={18} /> Medication Risk</button></li>
            <li><button type="button" onClick={() => setStaffSection('logActivities')} style={navBtn(staffSection === 'logActivities')} {...sidebarBtnHoverHandlers}><Camera size={18} /> Log Activities</button></li>
            {role === 'ADMIN' && (
              <li>
                <button type="button" onClick={() => setStaffSection('manageShifts')} style={navBtn(staffSection === 'manageShifts')}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="16"/>
                    <line x1="8" y1="12" x2="16" y2="12"/>
                  </svg>
                  Manage Shifts
                </button>
              </li>
            )}
            {role === 'CAREGIVER' && (
              <li>
                <button type="button" onClick={() => setStaffSection('shiftHandover')} style={navBtn(staffSection === 'shiftHandover')}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '0.5rem' }}>
                    <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/>
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                    <line x1="12" y1="19" x2="12" y2="22"/>
                  </svg>
                  Shift Handover
                </button>
              </li>
            )}
          </ul>
        </nav>
        <div style={logoutDockStyle}>
          <button
            onClick={onLogout}
            style={logoutBtnStyle}
            onMouseEnter={(event) => {
              event.currentTarget.style.transform = 'translateY(-1px)';
              event.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.14)';
            }}
            onMouseLeave={(event) => {
              event.currentTarget.style.transform = 'translateY(0)';
              event.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.06)';
            }}
          >
            <LogOut size={18} /> Sign Out
          </button>
        </div>
      </aside>

      <main style={{ flex: 1, padding: '3rem', overflowY: 'auto' }}>
        {staffSection === 'combi' ? (
          <div style={{ margin: '-3rem' }}>
            <SocialInteraction
              token={token}
              onLogout={onLogout}
              title="Social Interaction"
              description="The combined social-isolation model is now reachable from the caregiver sidebar."
            />
          </div>
        ) :staffSection === 'shiftHandover' && role === 'CAREGIVER' ? (  
            <div>
              <header style={{ marginBottom: '3rem' }}>
                <h1 style={{ color: 'var(--midnight-green)', margin: 0 }}> Shift Handover</h1>
                <p style={{ color: 'var(--text-light)', margin: 0 }}>Voice-to-Text for caregivers - Record handover notes between shifts</p>
              </header>
              <VoiceRecorder onSuccess={handleRecordingSuccess} />
              <hr style={{ margin: '30px 0' }} />
              <ReportsDashboard refreshTrigger={refreshKey} />
            </div>
        ) :staffSection === 'manageShifts' && role === 'ADMIN' ? (
          <div>
            <header style={{ marginBottom: '3rem' }}>
              <h1 style={{ color: 'var(--midnight-green)', margin: 0 }}> Shift Management</h1>
              <p style={{ color: 'var(--text-light)', margin: 0 }}>Configure shift hours for the retirement home</p>
            </header>
            <ShiftManagement />
          </div>
        ) : staffSection === 'logActivities' ? (
          <div style={{ padding: '0' }}>
            {/* Header */}
            <header style={{ marginBottom: '2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
              <div>
                <h1 style={{ color: 'var(--midnight-green)', margin: 0 }}>Log Activities</h1>
                <p style={{ color: 'var(--text-light)', margin: 0 }}>Camera-based detection and activity summaries</p>
              </div>
            </header>

            {/* Sub-tab bar */}
            <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '2rem', flexWrap: 'wrap' }}>
              {[
                { key: 'camera', icon: <Camera size={16} />, label: 'Camera Detection' },
                { key: 'summary', icon: <FileText size={16} />, label: 'Summary Generation' },
              ].map(({ key, icon, label }) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setLogActivitiesTab(key)}
                  style={logTabBtnStyle(logActivitiesTab === key)}
                >
                  {icon} {label}
                </button>
              ))}
            </div>

            {/* ── Camera Detection tab ─────────────────────────────────── */}
            {logActivitiesTab === 'camera' && (
              <div style={{ display: 'grid', gap: '1rem' }}>
                {/* Error banners */}
                {runModelsError && (
                  <div style={logAlertStyle('error')}>{runModelsError}</div>
                )}
                {cameraDetectionError && (
                  <div style={logAlertStyle('error')}>{cameraDetectionError}</div>
                )}
                {localCameraError && (
                  <div style={logAlertStyle('error')}>{localCameraError}</div>
                )}
                {runModelsMessage && (
                  <div style={logAlertStyle('success')}>{runModelsMessage}</div>
                )}

                {/* Live camera screen */}
                <div style={{ ...sectionCardStyle }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap' }}>
                    <h3 style={{ color: 'var(--midnight-green)', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <Camera size={18} /> Live Camera Screen
                    </h3>
                    <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center', flexWrap: 'wrap' }}>
                      <select
                        style={{ border: '1px solid #D7E3EA', borderRadius: '8px', padding: '8px 12px', fontSize: '0.9rem', color: 'var(--midnight-green)', backgroundColor: '#F9FCFE', minWidth: '200px' }}
                        value={selectedLocalCameraId}
                        onChange={(e) => setSelectedLocalCameraId(e.target.value)}
                        disabled={!localCameras.length}
                      >
                        {!localCameras.length && <option value="">No PC camera available</option>}
                        {localCameras.map((cam) => (
                          <option key={cam.id} value={cam.id}>{cam.label}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div style={{ ...logInsetPanelStyle, marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1.5rem', flexWrap: 'wrap' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '1rem', flex: 1 }}>
                      <div>
                        <p style={{ margin: '0 0 0.2rem', color: 'var(--text-light)', fontSize: '0.82rem' }}>Location</p>
                        <p style={{ margin: 0, color: 'var(--midnight-green)', fontWeight: 'bold', fontSize: '0.95rem' }}>
                          {selectedLogCamera?.location || (localCameras.length ? 'PC Camera' : 'No camera selected')}
                        </p>
                      </div>
                      <div>
                        <p style={{ margin: '0 0 0.2rem', color: 'var(--text-light)', fontSize: '0.82rem' }}>PC Cameras</p>
                        <p style={{ margin: 0, color: 'var(--midnight-green)', fontWeight: 'bold', fontSize: '0.95rem' }}>
                          {localCameras.length ? `${localCameras.length} device(s) detected` : 'None detected'}
                        </p>
                      </div>
                      <div>
                        <p style={{ margin: '0 0 0.2rem', color: 'var(--text-light)', fontSize: '0.82rem' }}>Detection mode</p>
                        <p style={{ margin: 0, fontWeight: 'bold', fontSize: '0.95rem', color: detectionModeColor }}>{detectionModeLabel}</p>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                      <button
                        type="button"
                        onClick={handleStartCameraAndModels}
                        disabled={busyStartingModels || busyStoppingModels}
                        style={{ border: 'none', borderRadius: '12px', padding: '0.8rem 1.5rem', fontWeight: 'bold', fontSize: '0.95rem', cursor: (busyStartingModels || busyStoppingModels) ? 'not-allowed' : 'pointer', backgroundColor: 'var(--moonstone)', color: 'white', opacity: (busyStartingModels || busyStoppingModels) ? 0.5 : 1, whiteSpace: 'nowrap' }}
                      >
                        {busyStartingModels ? '⏳ Starting...' : '▶ Start Models'}
                      </button>
                      <button
                        type="button"
                        onClick={handleStopModels}
                        disabled={busyStoppingModels}
                        style={{ border: 'none', borderRadius: '12px', padding: '0.8rem 1.25rem', fontWeight: 'bold', fontSize: '0.95rem', cursor: busyStoppingModels ? 'not-allowed' : 'pointer', backgroundColor: '#C2410C', color: 'white', opacity: busyStoppingModels ? 0.55 : 1, whiteSpace: 'nowrap' }}
                      >
                        {busyStoppingModels ? '⏳ Stopping...' : '■ Stop + Get Summary'}
                      </button>
                    </div>
                  </div>

                  {/* Live preview */}
                  {!localCameras.length ? (
                    <EmptyLogPanel title="No camera selected" message="Connect a PC camera to start detection models." />
                  ) : (
                    <div style={{ display: 'grid', gap: '1rem' }}>
                      <div style={{ width: '100%', minHeight: '260px', borderRadius: '14px', backgroundColor: '#F9FCFE', color: 'var(--midnight-green)', padding: '1rem', display: 'grid', placeItems: 'center', border: '1px solid #D7E3EA' }}>
                        <div style={{ textAlign: 'center', width: '100%' }}>
                          <p style={{ margin: 0, fontWeight: 'bold', color: 'var(--midnight-green)' }}>
                            {localCameras.find((c) => c.id === selectedLocalCameraId)?.label || 'PC Camera'}
                          </p>
                          <p style={{ margin: '0.45rem 0 1rem', fontSize: '0.88rem', color: 'var(--text-light)' }}>
                            Pipeline video mirrored from Python window
                          </p>
                          <div style={{ display: 'grid', gap: '0.75rem', maxWidth: '720px', margin: '0 auto' }}>
                            <div style={{ width: '100%', aspectRatio: '16 / 9', borderRadius: '12px', overflow: 'hidden', border: '1px solid #D7E3EA', backgroundColor: '#EAF3F7' }}>
                              {livePreviewUrl ? (
                                <img src={livePreviewUrl} alt="Live pipeline preview" style={{ width: '100%', height: '100%', objectFit: 'cover', backgroundColor: '#EAF3F7' }} />
                              ) : (
                                <div style={{ width: '100%', height: '100%', backgroundColor: '#EAF3F7' }} />
                              )}
                            </div>
                            <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.85rem' }}>Model output window stays on PC; this page mirrors the same frames.</p>
                          </div>
                        </div>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '0.9rem' }}>
                        <div style={logInfoTileStyle}>
                          <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.85rem' }}>Detection status</p>
                          <p style={{ margin: '0.25rem 0 0', color: isTrueDetectionRunning ? '#0F766E' : '#B45309', fontWeight: 'bold' }}>
                            {isTrueDetectionRunning ? 'Active' : 'Not active yet'}
                          </p>
                        </div>
                        <div style={logInfoTileStyle}>
                          <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.85rem' }}>Resident detections</p>
                          <p style={{ margin: '0.25rem 0 0', color: 'var(--midnight-green)', fontWeight: 'bold' }}>{cameraDetectionPayload?.resident_detections?.length || 0}</p>
                        </div>
                        <div style={logInfoTileStyle}>
                          <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.85rem' }}>Recent events</p>
                          <p style={{ margin: '0.25rem 0 0', color: 'var(--midnight-green)', fontWeight: 'bold' }}>{cameraDetectionPayload?.recent_camera_events?.length || 0}</p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Live detection info */}
                <div style={{ ...sectionCardStyle }}>
                  <h3 style={{ color: 'var(--midnight-green)', marginTop: 0, marginBottom: '0.8rem' }}>Live Detection Info</h3>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                    <div>
                      <p style={{ margin: '0 0 0.6rem', color: 'var(--midnight-green)', fontWeight: 'bold', fontSize: '0.9rem' }}>Resident Detections</p>
                      {cameraDetectionPayload?.resident_detections?.length ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '320px', overflowY: 'auto' }}>
                          {cameraDetectionPayload.resident_detections.map((d) => (
                            <div key={`${d.person_id}-${d.last_seen}`} style={{ ...logInfoTileStyle, backgroundColor: '#F9FCFE' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', alignItems: 'flex-start' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                                  {d.resident_photo_url ? (
                                    <img src={d.resident_photo_url} alt={d.name} style={{ width: 38, height: 38, borderRadius: '50%', objectFit: 'cover', border: '2px solid var(--moonstone)', flexShrink: 0 }} />
                                  ) : (
                                    <div style={{ width: 38, height: 38, borderRadius: '50%', backgroundColor: 'var(--moonstone)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 'bold', fontSize: '0.9rem', flexShrink: 0 }}>
                                      {(d.name || '?')[0].toUpperCase()}
                                    </div>
                                  )}
                                  <p style={{ margin: '0 0 0.25rem', fontWeight: 'bold', color: 'var(--midnight-green)' }}>{d.name}</p>
                                </div>
                                <span style={{ fontSize: '0.75rem', fontWeight: 'bold', padding: '4px 8px', borderRadius: '999px', backgroundColor: d.detection_source === 'machine7' ? '#DCFCE7' : '#FEF3C7', color: d.detection_source === 'machine7' ? '#166534' : '#92400E' }}>
                                  {d.detection_source === 'machine7' ? 'True detection' : 'Compatibility'}
                                </span>
                              </div>
                              <p style={{ margin: '0 0 0.2rem', color: 'var(--text-dark)', fontSize: '0.9rem' }}>Detected at: {d.detected_location || d.camera_location || d.area || 'Unknown'}</p>
                              <p style={{ margin: '0 0 0.2rem', color: 'var(--text-dark)', fontSize: '0.9rem' }}>Activity: {d.activity}</p>
                              <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.85rem' }}>Last seen: {formatTimestamp(d.last_seen)}</p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <EmptyLogPanel title="No detections yet" message="Pipeline active — no resident detected yet." />
                      )}
                    </div>
                    <div>
                      <p style={{ margin: '0 0 0.6rem', color: 'var(--midnight-green)', fontWeight: 'bold', fontSize: '0.9rem' }}>Recent Camera Events</p>
                      {cameraDetectionPayload?.recent_camera_events?.length ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '320px', overflowY: 'auto' }}>
                          {cameraDetectionPayload.recent_camera_events.map((ev, idx) => (
                            <div key={`${ev.created_at || idx}-${idx}`} style={{ padding: '0.9rem', borderLeft: '4px solid var(--moonstone)', backgroundColor: '#F9FCFE', borderRadius: '0 12px 12px 0', borderTop: '1px solid #D7E3EA', borderRight: '1px solid #D7E3EA', borderBottom: '1px solid #D7E3EA' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.35rem' }}>
                                {ev.resident_photo_url ? (
                                  <img src={ev.resident_photo_url} alt={ev.resident} style={{ width: 36, height: 36, borderRadius: '50%', objectFit: 'cover', border: '2px solid var(--moonstone)', flexShrink: 0 }} />
                                ) : (
                                  <div style={{ width: 36, height: 36, borderRadius: '50%', backgroundColor: 'var(--moonstone)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 'bold', fontSize: '0.85rem', flexShrink: 0 }}>
                                    {(ev.resident || '?')[0].toUpperCase()}
                                  </div>
                                )}
                                <p style={{ margin: 0, fontWeight: 'bold', color: 'var(--midnight-green)' }}>{ev.resident}</p>
                              </div>
                              <p style={{ margin: '0 0 0.2rem', color: 'var(--text-dark)', fontSize: '0.9rem' }}>{ev.summary_text || 'No summary text.'}</p>
                              <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.85rem' }}>{ev.location} | {formatTimestamp(ev.created_at)}</p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <EmptyLogPanel title="No camera events yet" message="Events will appear here while monitoring is running." />
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ── Summary Generation tab ────────────────────────────────── */}
            {logActivitiesTab === 'summary' && (
              <div style={{ display: 'grid', gap: '1rem' }}>
                <div style={{ ...sectionCardStyle }}>
                  <h3 style={{ color: 'var(--midnight-green)', margin: 0 }}>Generated Summaries</h3>
                  <p style={{ color: 'var(--text-light)', margin: '0.25rem 0 0' }}>Review generated summaries from monitoring sessions.</p>
                </div>

                {generateMessage && (
                  <div style={logAlertStyle('success')}>{generateMessage}</div>
                )}

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div style={{ ...sectionCardStyle }}>
                    <h3 style={{ color: 'var(--midnight-green)', marginTop: 0, marginBottom: '0.8rem' }}>Summary Snapshots</h3>
                    {pipelineSummary.length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '500px', overflowY: 'auto' }}>
                        {pipelineSummary.map((item) => (
                          <div key={item.person_id} style={{ ...logInfoTileStyle, backgroundColor: '#F9FCFE' }}>
                            <strong style={{ color: 'var(--midnight-green)' }}>{item.name}</strong>
                            <p style={{ margin: '0.35rem 0', color: 'var(--text-dark)' }}>{item.summary_line}</p>
                            <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.85rem' }}>Top area: {item.top_area || 'N/A'}</p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <EmptyLogPanel title="No monitoring summaries" message="Start and stop detection to populate this page with summaries." />
                    )}
                  </div>

                  <div style={{ ...sectionCardStyle }}>
                    <h3 style={{ color: 'var(--midnight-green)', marginTop: 0, marginBottom: '0.8rem' }}>All Generated History</h3>
                    {pipelineHistory.length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '500px', overflowY: 'auto' }}>
                        {pipelineHistory.map((entry) => (
                          <div key={entry.id} style={{ padding: '1rem', borderLeft: '4px solid var(--moonstone)', backgroundColor: '#F9FCFE', borderRadius: '0 10px 10px 0', borderTop: '1px solid #D7E3EA', borderRight: '1px solid #D7E3EA', borderBottom: '1px solid #D7E3EA' }}>
                            <p style={{ margin: '0 0 0.35rem', fontWeight: 'bold', color: 'var(--midnight-green)' }}>{entry.name}</p>
                            <p style={{ margin: '0 0 0.25rem', color: 'var(--text-dark)' }}>{formatHistoryEntry(entry)}</p>
                            <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.85rem' }}>Top area: {entry.location} | {formatTimestamp(entry.created_at)}</p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <EmptyLogPanel title="No generated history" message="Generated summaries will appear here after monitoring activity." />
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : staffSection === 'wandering' ? (
          <div style={{ margin: '-3rem' }}>
            <WanderingDetection token={token} onLogout={onLogout} />
          </div>
        ) : (
          <div>
          {/* Header - caché pour la page meals */}
          {staffSection !== 'meals' && (
            <header style={{ marginBottom: '3rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
              <div>
                <h1 style={{ color: 'var(--midnight-green)', margin: 0 }}>Caregiver Dashboard</h1>
                <p style={{ color: 'var(--text-light)', margin: 0 }}>
                  {staffSection === 'livefeed' ? 'Monitor live aggression detection feeds' :
                    staffSection === 'gait' ? 'Review gait-analysis results and launch new recordings' :
                    staffSection === 'wandering' ? 'Review wandering risk scores, trajectories, and generated reports' :
                    staffSection === 'residents-db' ? 'Manage resident records, photos, and face-recognition data' :
                    staffSection === 'incidents' ? 'View all facility incidents and history' :
                      'Review resident monitoring tools for your shift'}
                </p>
              </div>
              <NotificationBell token={token} compact dropdownAlign="top-right" />
            </header>
          )}

          {/* Header simplifié pour la page meals - seulement la cloche */}
          {staffSection === 'meals' && (
            <header style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'flex-end', alignItems: 'center' }}>
              <NotificationBell token={token} compact dropdownAlign="top-right" />
            </header>
          )}

            {staffSection === 'gait' ? (
              <GaitAnalysisPanel token={token} onLogout={onLogout} />
            ) : staffSection === 'medication' ? (
            <MedicationPanel token={token} onLogout={onLogout} />
            ) : staffSection === 'meals' ? (
              <MealAttendance token={token} role={role} onLogout={onLogout} />
            ) : staffSection === 'livefeed' ? (
              <div style={sectionCardStyle}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h3 style={{ color: 'var(--midnight-green)', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Eye size={18} color="#EA580C" /> Live Aggression Detection
                  </h3>
                  <div style={{ display: 'flex', gap: '0.75rem' }}>
                    {!streamRunning ? (
                      <button
                        onClick={handleStartStream}
                        disabled={streamLoading}
                        style={{ padding: '8px 20px', backgroundColor: '#059669', color: 'white', border: 'none', borderRadius: '8px', cursor: streamLoading ? 'not-allowed' : 'pointer', fontWeight: 600, fontSize: '0.9rem', opacity: streamLoading ? 0.6 : 1, transition: 'all 0.2s' }}
                      >
                        {streamLoading ? 'Starting...' : 'Start Stream'}
                      </button>
                    ) : (
                      <button
                        onClick={handleStopStream}
                        disabled={streamLoading}
                        style={{ padding: '8px 20px', backgroundColor: '#DC2626', color: 'white', border: 'none', borderRadius: '8px', cursor: streamLoading ? 'not-allowed' : 'pointer', fontWeight: 600, fontSize: '0.9rem', opacity: streamLoading ? 0.6 : 1, transition: 'all 0.2s' }}
                      >
                        {streamLoading ? 'Stopping...' : 'Stop Stream'}
                      </button>
                    )}
                  </div>
                </div>

                {streamError && (
                  <div style={{ backgroundColor: '#FEE2E2', color: '#B91C1C', padding: '12px', borderRadius: '8px', marginBottom: '1rem', border: '1px solid #F87171', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <AlertCircle size={20} />
                    <span style={{ fontWeight: 500 }}>{streamError}</span>
                  </div>
                )}

                {streamRunning ? (
                  <div style={{ position: 'relative', width: '100%', borderRadius: '12px', overflow: 'hidden', backgroundColor: '#000', border: '2px solid var(--midnight-green)' }}>
                    <img
                      key={streamKey}
                      src={`${API_BASE}/stream/aggression/feed/?t=${streamKey}`}
                      alt="Live aggression detection feed"
                      onLoad={() => setStreamError('')}
                      onError={() => {
                        setStreamRunning(false);
                        setStreamError('Aggression stream lost access to the webcam. If the meal camera is active, stop it first and start the aggression stream again.');
                      }}
                      style={{ width: '100%', display: 'block' }}
                    />
                    <div style={{ position: 'absolute', top: '10px', right: '10px', display: 'flex', alignItems: 'center', gap: '6px', backgroundColor: 'rgba(220, 38, 38, 0.9)', padding: '4px 12px', borderRadius: '20px' }}>
                      <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#fff', animation: 'pulse 1.5s infinite' }} />
                      <span style={{ color: 'white', fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.05em' }}>LIVE</span>
                    </div>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '400px', backgroundColor: '#111827', borderRadius: '12px', border: '2px dashed rgba(255,255,255,0.1)' }}>
                    <Video size={64} color="rgba(255,255,255,0.2)" style={{ marginBottom: '1rem' }} />
                    <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '1.1rem', margin: 0 }}>Click "Start Stream" to begin live monitoring</p>
                    <p style={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.85rem', marginTop: '0.5rem' }}>Camera: CAM_01 - Aggression LSTM + MediaPipe Pose</p>
                  </div>
                )}

                <div style={{ marginTop: '1rem', padding: '1rem', backgroundColor: 'var(--alice-blue)', borderRadius: '8px', display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
                  <div><span style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>Model</span><p style={{ margin: 0, fontWeight: 600, color: 'var(--midnight-green)' }}>AggressionLSTM (15 features)</p></div>
                  <div><span style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>Threshold</span><p style={{ margin: 0, fontWeight: 600, color: 'var(--midnight-green)' }}>70%</p></div>
                  <div><span style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>Tracking</span><p style={{ margin: 0, fontWeight: 600, color: 'var(--midnight-green)' }}>Up to 3 persons</p></div>
                  <div><span style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>Auto-Report</span><p style={{ margin: 0, fontWeight: 600, color: '#059669' }}>Enabled (30s cooldown)</p></div>
                </div>
              </div>
            ) : staffSection === 'wandering' ? (
              <WanderingDetection token={token} onLogout={onLogout} />
            ) : staffSection === 'residents-db' ? (
              <ResidentsPage token={token} onLogout={onLogout} />
            ) : staffSection === 'diabetes' ? (
              <DiabetesMonitor token={token} onLogout={onLogout} />
            ) : staffSection === 'incidents' ? (
              <div style={sectionCardStyle}>
                <h3 style={{ color: 'var(--midnight-green)', margin: '0 0 1rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <ShieldAlert size={18} color="#EF4444" /> Facility Incidents
                </h3>
                {facilityIncidents.length > 0 ? (
                  <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    {facilityIncidents.map((inc) => {
                      const c = getIncidentColor(inc.type);
                      return (
                        <li key={inc.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', padding: '0.85rem 1rem', borderRadius: '8px', backgroundColor: c.bg, borderLeft: `4px solid ${c.border}` }}>
                          <div>
                            <p style={{ margin: 0, fontWeight: 700, color: c.text, fontSize: '0.9rem' }}>
                              {inc.type_display} ({inc.severity_display})
                            </p>
                            <p style={{ margin: '0.25rem 0 0 0', color: 'var(--text-dark)', fontSize: '0.85rem' }}>
                              Zone: {inc.zone?.name || 'Unknown'}
                            </p>
                          </div>
                          <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
                            {new Date(inc.timestamp).toLocaleString()}
                          </p>
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <p style={{ color: 'var(--text-light)', margin: 0 }}>No facility incidents yet.</p>
                )}
              </div>
            ) : (
              <div style={{ ...sectionCardStyle, textAlign: 'center', padding: '3rem' }}>
                <Users size={42} color="var(--moonstone)" style={{ marginBottom: '1rem' }} />
                <h2 style={{ color: 'var(--midnight-green)', marginBottom: '0.75rem' }}>Section removed</h2>
                <p style={{ color: 'var(--text-light)', fontSize: '1rem', margin: 0 }}>The old Assigned Residents page has been removed from this dashboard.</p>
              </div>
            )}
          </div>
        )}
      </main>
      <ChatbotWidget token={token} />
    </div>
  );
}

function FamilyDashboard({ token, onLogout }) {
  const [activePage, setActivePage] = useState('overview');
  const [data, setData] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const response = await axios.get(`${API_BASE}/mobile/activity-log/`, { headers: { Authorization: `Bearer ${token}` } });
        setData(response.data);
      } catch (err) {
        if (err.response?.status === 401) onLogout();
        else if (err.response?.status === 404) setErrorMsg('No residents assigned to your account yet.');
        else if (err.response?.status === 403) setErrorMsg('Access forbidden. You might not have the correct role permissions.');
        else setErrorMsg('An error occurred while fetching your dashboard.');
      } finally {
        setLoading(false);
      }
    };
    fetchDashboard();
  }, [token, onLogout]);

  if (loading) return <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--midnight-green)' }}><h2>Loading AI Telemetry...</h2></div>;

  const tempChartData = data ? [
    { name: 'Mon', gait: 0.8, social: data.average_social_score_7d - 5 || 50 },
    { name: 'Tue', gait: 0.9, social: data.average_social_score_7d + 2 || 55 },
    { name: 'Wed', gait: 1.0, social: data.average_social_score_7d - 1 || 52 },
    { name: 'Thu', gait: 0.9, social: data.average_social_score_7d + 5 || 60 },
    { name: 'Fri', gait: 0.7, social: data.average_social_score_7d - 3 || 45 },
    { name: 'Sat', gait: 0.85, social: data.average_social_score_7d || 53 },
    { name: 'Sun', gait: 0.92, social: data.average_social_score_7d + 1 || 55 },
  ] : [];

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: 'var(--alice-blue)' }}>
      <aside style={{ width: '260px', backgroundColor: 'var(--midnight-green)', color: 'white', display: 'flex', flexDirection: 'column', position: 'sticky', top: 0, height: '100vh', overflowY: 'auto' }}>
        <div style={{ padding: '1.5rem 2rem', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '8px', textDecoration: 'none', color: 'white', fontSize: '1.5rem', fontWeight: 'bold' }}>
            <img src="/LOGO_AURACARE.png" alt="AuraCare Logo" style={{ height: '40px' }} />
            AuraCare
          </Link>
        </div>
        <nav style={{ flex: 1, padding: '1rem' }}>
          <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', listStyle: 'none', padding: 0 }}>
            <li><button onClick={() => setActivePage('overview')} style={navBtn(activePage === 'overview')} {...sidebarBtnHoverHandlers}><Activity size={18} /> Overview</button></li>
            <li><button onClick={() => setActivePage('incidents')} style={navBtn(activePage === 'incidents')} {...sidebarBtnHoverHandlers}><ShieldAlert size={18} /> Incident Logs</button></li>
          </ul>
        </nav>
        <div style={logoutDockStyle}>
          <button
            onClick={onLogout}
            style={logoutBtnStyle}
            onMouseEnter={(event) => {
              event.currentTarget.style.transform = 'translateY(-1px)';
              event.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.14)';
            }}
            onMouseLeave={(event) => {
              event.currentTarget.style.transform = 'translateY(0)';
              event.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.06)';
            }}
          >
            <LogOut size={18} /> Sign Out
          </button>
        </div>
      </aside>

      <main style={{ flex: 1, overflowY: 'auto' }}>
        {activePage === 'overview' && (
          <div style={{ padding: '3rem' }}>
            {errorMsg ? (
              <div style={{ ...sectionCardStyle, textAlign: 'center', padding: '3rem' }}>
                <AlertCircle size={48} color="var(--cadet-gray)" style={{ marginBottom: '1rem' }} />
                <h2 style={{ color: 'var(--midnight-green)', marginBottom: '1rem' }}>Dashboard Unavailable</h2>
                <p style={{ color: 'var(--text-light)', fontSize: '1.1rem' }}>{errorMsg}</p>
                <p style={{ color: 'var(--text-light)', marginTop: '2rem' }}>Please contact an administrator to get access to specific residents.</p>
              </div>
            ) : (
              <>
                <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3rem' }}>
                  <div>
                    <h1 style={{ color: 'var(--midnight-green)', margin: 0 }}>Resident Overview</h1>
                    <p style={{ color: 'var(--text-light)', margin: 0 }}>Monitoring: {data?.resident_name}</p>
                  </div>
                  <div style={{ padding: '10px 20px', backgroundColor: 'white', borderRadius: 'var(--border-radius-sm)', boxShadow: 'var(--box-shadow)' }}>
                    <span style={{ color: 'var(--text-light)', fontSize: '0.9rem' }}>Status: </span>
                    <span style={{ color: 'var(--moonstone)', fontWeight: 'bold' }}>Active & Secure</span>
                  </div>
                </header>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '2rem', marginBottom: '3rem' }}>
                  <div style={sectionCardStyle}>
                    <h4 style={{ color: 'var(--text-light)', margin: 0 }}>Social Interaction Score</h4>
                    <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: 'var(--midnight-green)' }}>
                      {data?.average_social_score_7d ? data.average_social_score_7d.toFixed(1) : 'N/A'}
                    </div>
                    <p style={{ color: 'var(--moonstone)', fontSize: '0.9rem', margin: 0 }}>Last 7 Days Avg</p>
                  </div>
                  <div style={sectionCardStyle}>
                    <h4 style={{ color: 'var(--text-light)', margin: 0 }}>Recent Incidents</h4>
                    <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: '#EF4444' }}>{data?.recent_incidents?.length || 0}</div>
                    <p style={{ color: 'var(--text-light)', fontSize: '0.9rem', margin: 0 }}>Pending review</p>
                  </div>
                  <div style={sectionCardStyle}>
                    <h4 style={{ color: 'var(--text-light)', margin: 0 }}>Active Monitors</h4>
                    <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: 'var(--moonstone)' }}>7</div>
                    <p style={{ color: 'var(--text-light)', fontSize: '0.9rem', margin: 0 }}>All Zones Nominal</p>
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '2rem' }}>
                  <div style={{ ...sectionCardStyle, padding: '2rem' }}>
                    <h3 style={{ color: 'var(--midnight-green)', marginBottom: '1.5rem' }}>Weekly Telemetry Trends</h3>
                    <div style={{ height: 300 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={tempChartData}>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E9F1F6" />
                          <XAxis dataKey="name" axisLine={false} tickLine={false} />
                          <YAxis yAxisId="left" axisLine={false} tickLine={false} />
                          <YAxis yAxisId="right" orientation="right" axisLine={false} tickLine={false} />
                          <Tooltip />
                          <Legend />
                          <Line yAxisId="left" type="monotone" dataKey="social" stroke="var(--moonstone)" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 8 }} name="Social Score" />
                          <Line yAxisId="right" type="monotone" dataKey="gait" stroke="var(--midnight-green)" strokeWidth={3} dot={{ r: 4 }} name="Gait Speed (m/s)" />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                  <div style={{ ...sectionCardStyle, padding: '2rem' }}>
                    <h3 style={{ color: 'var(--midnight-green)', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <AlertCircle color="#EF4444" /> Incident Feed
                    </h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                      {data?.recent_incidents && data.recent_incidents.length > 0 ? (
                        data.recent_incidents.map((incident, idx) => {
                          const c = getIncidentColor(incident.type);
                          return (
                            <div key={idx} style={{ padding: '1rem', borderLeft: `4px solid ${c.border}`, backgroundColor: c.bg, borderRadius: '0 var(--border-radius-sm) var(--border-radius-sm) 0' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
                                {incident.resident_photo_url ? (
                                  <img src={incident.resident_photo_url} alt={incident.resident_name || 'Resident'} style={{ width: 36, height: 36, borderRadius: '50%', objectFit: 'cover', border: `2px solid ${c.border}`, flexShrink: 0 }} />
                                ) : (
                                  <div style={{ width: 36, height: 36, borderRadius: '50%', backgroundColor: c.border, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 'bold', fontSize: '0.85rem', flexShrink: 0 }}>
                                    {(incident.resident_name || '?')[0].toUpperCase()}
                                  </div>
                                )}
                                <p style={{ margin: 0, fontWeight: 'bold', color: c.text }}>{incident.type_display} detected</p>
                              </div>
                              {incident.resident_name && <p style={{ margin: '0 0 0.25rem', fontSize: '0.85rem', color: c.text, fontWeight: 600 }}>Resident: {incident.resident_name}</p>}
                              <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-light)' }}>Zone: {incident.zone?.name || 'Unknown'}</p>
                              <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-light)' }}>{new Date(incident.timestamp).toLocaleString()}</p>
                            </div>
                          );
                        })
                      ) : (
                        <p style={{ color: 'var(--text-light)', fontStyle: 'italic' }}>No recent incidents.</p>
                      )}
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {activePage === 'incidents' && (
          <div style={{ padding: '3rem' }}>
            <header style={{ marginBottom: '3rem' }}>
              <h1 style={{ color: 'var(--midnight-green)', margin: 0 }}>Incident Logs</h1>
              <p style={{ color: 'var(--text-light)', margin: 0 }}>Full history of detected incidents</p>
            </header>
            {errorMsg ? (
              <div style={{ ...sectionCardStyle, textAlign: 'center', padding: '3rem' }}>
                <AlertCircle size={48} color="var(--cadet-gray)" style={{ marginBottom: '1rem' }} />
                <h2 style={{ color: 'var(--midnight-green)', marginBottom: '1rem' }}>Dashboard Unavailable</h2>
                <p style={{ color: 'var(--text-light)', fontSize: '1.1rem' }}>{errorMsg}</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {data?.recent_incidents && data.recent_incidents.length > 0 ? (
                  data.recent_incidents.map((incident, idx) => {
                    const c = getIncidentColor(incident.type);
                    return (
                      <div key={idx} style={{ padding: '1.5rem', borderLeft: `4px solid ${c.border}`, backgroundColor: 'white', borderRadius: '0 var(--border-radius-sm) var(--border-radius-sm) 0', boxShadow: 'var(--box-shadow)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem', gap: '1rem' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                            {incident.resident_photo_url ? (
                              <img src={incident.resident_photo_url} alt={incident.resident_name || 'Resident'} style={{ width: 44, height: 44, borderRadius: '50%', objectFit: 'cover', border: `2px solid ${c.border}`, flexShrink: 0 }} />
                            ) : (
                              <div style={{ width: 44, height: 44, borderRadius: '50%', backgroundColor: c.badge, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 'bold', fontSize: '1rem', flexShrink: 0 }}>
                                {(incident.resident_name || '?')[0].toUpperCase()}
                              </div>
                            )}
                            <div>
                              <strong style={{ color: c.text }}>{incident.type_display}</strong>
                              {incident.resident_name && <p style={{ margin: '0.1rem 0 0', fontSize: '0.85rem', color: 'var(--text-dark)', fontWeight: 600 }}>{incident.resident_name}</p>}
                            </div>
                          </div>
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-light)', whiteSpace: 'nowrap' }}>{new Date(incident.timestamp).toLocaleString()}</span>
                        </div>
                        <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--text-dark)' }}>{incident.description || 'No description provided.'}</p>
                        <p style={{ margin: '0.25rem 0 0', fontSize: '0.8rem', color: 'var(--text-light)' }}>Zone: {incident.zone?.name || 'Unknown'}</p>
                      </div>
                    );
                  })
                ) : (
                  <div style={{ ...sectionCardStyle, textAlign: 'center', padding: '3rem' }}>
                    <ShieldAlert size={48} color="var(--moonstone)" style={{ marginBottom: '1rem', opacity: 0.4 }} />
                    <p style={{ color: 'var(--text-light)' }}>No incidents recorded yet.</p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>
      <ChatbotWidget token={token} />
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const token = localStorage.getItem('access_token');

  if (!token) return <Navigate to="/login" />;

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    navigate('/login');
  };

  let role = 'FAMILY';
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(window.atob(base64).split('').map((c) => `%${(`00${c.charCodeAt(0).toString(16)}`).slice(-2)}`).join(''));
    const decoded = JSON.parse(jsonPayload);
    if (decoded && decoded.role) role = decoded.role;
  } catch (err) {
    console.error('Invalid token format', err);
  }

  if (role === 'CAREGIVER' || role === 'ADMIN') {
    return <StaffDashboard token={token} onLogout={handleLogout} role={role} />;
  }
  return <FamilyDashboard token={token} onLogout={handleLogout} />;
}
