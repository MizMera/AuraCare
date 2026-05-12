import { useEffect, useRef, useState } from 'react';
import { Navigate, useNavigate, useLocation, Link } from 'react-router-dom';
import axios from 'axios';
import { LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import {
  LogOut,
  Activity,
  AlertCircle,
  ShieldAlert,
  Users,
  HeartPulse,
  Camera,
  FileText,
  Radar,
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000/api';

const shellStyle = { display: 'flex', minHeight: '100vh', backgroundColor: 'var(--alice-blue)' };
const sidebarStyle = { width: '260px', backgroundColor: 'var(--midnight-green)', color: 'white', display: 'flex', flexDirection: 'column' };
const panelStyle = { backgroundColor: 'white', padding: '1.5rem', borderRadius: 'var(--border-radius)', boxShadow: 'var(--box-shadow)' };
const inputStyle = { width: '100%', padding: '0.85rem 1rem', borderRadius: '12px', border: '1px solid #D1D5DB', fontSize: '0.95rem' };
const actionButtonStyle = { border: 'none', borderRadius: '12px', padding: '0.9rem 1rem', fontWeight: 'bold', cursor: 'pointer' };
const subtlePanelStyle = { ...panelStyle, backgroundColor: '#F8FBFC', border: '1px solid rgba(0, 69, 84, 0.08)' };
const tabButtonStyle = {
  border: '1px solid #D1D5DB',
  borderRadius: '999px',
  padding: '0.55rem 1rem',
  fontSize: '0.9rem',
  fontWeight: 'bold',
  cursor: 'pointer',
};

function authConfig(token) {
  return {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  };
}

function formatTimestamp(value) {
  if (!value) {
    return 'No recent signal';
  }

  const numericValue = typeof value === 'number' ? value * 1000 : Date.parse(value);
  if (Number.isNaN(numericValue)) {
    return 'No recent signal';
  }
  return new Date(numericValue).toLocaleString();
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

  // Parse encoded bracket [standing=X,sitting=Y,walking=Z]
  const bracketMatch = rawText.match(/\[([a-z]+=\d+(?:\.\d+)?(?:,[a-z]+=\d+(?:\.\d+)?)*)\]/);
  if (bracketMatch) {
    const parts = {};
    bracketMatch[1].split(',').forEach(p => {
      const [act, val] = p.split('=');
      if (act && val) parts[act.trim()] = parseFloat(val);
    });
    const standing = parts.standing || 0;
    const sitting = parts.sitting || 0;
    const walking = parts.walking || 0;
    const total = standing + sitting + walking;
    return (
      `The resident ${name} was detected in ${location} for ${formatDurationWords(total)}. ` +
      `He was standing for ${formatDurationWords(standing)}. ` +
      `He was sitting for ${formatDurationWords(sitting)}. ` +
      `He was walking for ${formatDurationWords(walking)}.`
    );
  }

  // Fallback: clean the bracket if no match, return raw text
  return rawText.replace(/\[.*?\]/g, '').trim() || 'No summary available.';
}

function getCameraSourceType(source) {
  if (!source) {
    return 'none';
  }
  const normalized = String(source).trim().toLowerCase();
  if (normalized.startsWith('rtsp://')) {
    return 'rtsp';
  }
  if (normalized.endsWith('.m3u8') || normalized.includes('.m3u8?')) {
    return 'hls';
  }
  if (normalized.endsWith('.mp4') || normalized.includes('.mp4?')) {
    return 'video';
  }
  if (normalized.endsWith('.mjpg') || normalized.endsWith('.mjpeg') || normalized.includes('/mjpg') || normalized.includes('/mjpeg')) {
    return 'mjpeg';
  }
  if (normalized.startsWith('http://') || normalized.startsWith('https://')) {
    return 'web';
  }
  return 'unknown';
}

function MetricCard({ title, value, subtitle, accent = 'var(--midnight-green)' }) {
  return (
    <div style={panelStyle}>
      <h4 style={{ color: 'var(--text-light)', margin: 0 }}>{title}</h4>
      <div style={{ fontSize: '2.2rem', fontWeight: 'bold', color: accent }}>{value}</div>
      <p style={{ color: 'var(--text-light)', fontSize: '0.9rem', margin: 0 }}>{subtitle}</p>
    </div>
  );
}

function EmptyPanel({ title, message, detail }) {
  return (
    <div style={{ ...subtlePanelStyle, textAlign: 'center', padding: '2rem' }}>
      <h3 style={{ color: 'var(--midnight-green)', marginTop: 0, marginBottom: '0.5rem' }}>{title}</h3>
      <p style={{ color: 'var(--text-light)', margin: 0 }}>{message}</p>
      {detail ? <p style={{ color: 'var(--text-light)', margin: '0.75rem 0 0 0', fontSize: '0.9rem' }}>{detail}</p> : null}
    </div>
  );
}

function StaffDashboard({ token, onLogout }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [residents, setResidents] = useState([]);
  const [staffErrorMsg, setStaffErrorMsg] = useState('');
  const [monitoringError, setMonitoringError] = useState('');
  const [loading, setLoading] = useState(true);
  const [generateMessage, setGenerateMessage] = useState('');
  const [busyStartingModels, setBusyStartingModels] = useState(false);
  const [busyStoppingModels, setBusyStoppingModels] = useState(false);
  const [runModelsMessage, setRunModelsMessage] = useState('');
  const [runModelsError, setRunModelsError] = useState('');
  const [monitoringResidents, setMonitoringResidents] = useState([]);
  const [pipelineStatus, setPipelineStatus] = useState(null);
  const [pipelineSummary, setPipelineSummary] = useState([]);
  const [pipelineHistory, setPipelineHistory] = useState([]);
  const [cameras, setCameras] = useState([]);
  const [selectedCameraId, setSelectedCameraId] = useState('');
  const [selectedCameraIds, setSelectedCameraIds] = useState([]);
  const [newCameraName, setNewCameraName] = useState('');
  const [newCameraSource, setNewCameraSource] = useState('');
  const [newCameraLocation, setNewCameraLocation] = useState('');
  const [newCameraActive, setNewCameraActive] = useState(true);
  const [cameraCreateMessage, setCameraCreateMessage] = useState('');
  const [cameraCreateError, setCameraCreateError] = useState('');
  const [localCameras, setLocalCameras] = useState([]);
  const [selectedLocalCameraId, setSelectedLocalCameraId] = useState('');
  const [localCameraError, setLocalCameraError] = useState('');
  const [localCameraReady, setLocalCameraReady] = useState(false);
  const [livePreviewUrl, setLivePreviewUrl] = useState('');
  const [cameraDetectionPayload, setCameraDetectionPayload] = useState(null);
  const [cameraDetectionError, setCameraDetectionError] = useState('');
  const [enrollName, setEnrollName] = useState('');
  const [enrollResidentId, setEnrollResidentId] = useState('');
  const [enrollFiles, setEnrollFiles] = useState([]);
  const [editResidentKey, setEditResidentKey] = useState('');
  const [editResidentName, setEditResidentName] = useState('');
  const [editResidentCode, setEditResidentCode] = useState('');
  const [deleteResidentKey, setDeleteResidentKey] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const [actionError, setActionError] = useState('');
  const localVideoRef = useRef(null);
  const localStreamRef = useRef(null);
  const hasMonitoringResidents = monitoringResidents.length > 0;
  const isLogActivitiesRoute = location.pathname.startsWith('/dashboard/log-activities');
  const activeOutlogaPage = location.pathname.endsWith('/resident-entry')
    ? 'entry'
    : location.pathname.endsWith('/camera-detection')
      ? 'camera'
      : location.pathname.endsWith('/summary-generation')
        ? 'summary'
        : '';

  const stopLocalStream = () => {
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach((track) => track.stop());
      localStreamRef.current = null;
    }
    if (localVideoRef.current) {
      localVideoRef.current.srcObject = null;
    }
    setLocalCameraReady(false);
  };

  const attachLocalStreamToVideo = async () => {
    if (!localVideoRef.current || !localStreamRef.current) {
      return;
    }

    if (localVideoRef.current.srcObject !== localStreamRef.current) {
      localVideoRef.current.srcObject = localStreamRef.current;
    }

    try {
      await localVideoRef.current.play();
    } catch {
      // Keep silent; autoplay can be blocked transiently and recover on user interaction.
    }
  };

  const fetchDashboard = async ({ keepLoading = false } = {}) => {
    if (!keepLoading) {
      setLoading(true);
    }

    const responses = await Promise.allSettled([
      axios.get(`${API_BASE}/mobile/dashboard/`, authConfig(token)),
      axios.get(`${API_BASE}/monitoring/residents/`, authConfig(token)),
      axios.get(`${API_BASE}/monitoring/status/`, authConfig(token)),
      axios.get(`${API_BASE}/monitoring/cameras/`, authConfig(token)),
      axios.get(`${API_BASE}/monitoring/summary/?window_hours=24`, authConfig(token)),
      axios.get(`${API_BASE}/monitoring/history/?limit=120`, authConfig(token)),
    ]);

    const unauthorized = responses.find(
      (result) => result.status === 'rejected' && result.reason?.response?.status === 401,
    );
    if (unauthorized) {
      onLogout();
      return;
    }

    const [mobileResult, residentResult, statusResult, cameraResult, summaryResult, historyResult] = responses;

    if (mobileResult.status === 'fulfilled') {
      setResidents(Array.isArray(mobileResult.value.data) ? mobileResult.value.data : []);
      setStaffErrorMsg('');
    } else {
      setResidents([]);
      if (mobileResult.reason?.response?.status === 404) {
        setStaffErrorMsg('No residents are directly assigned in the original dashboard view. Monitoring data is still available below.');
      } else if (mobileResult.reason?.response?.status === 403) {
        setStaffErrorMsg('The original mobile dashboard is restricted for this account. Monitoring data is still available below.');
      } else {
        setStaffErrorMsg('The original resident cards could not be loaded. Monitoring data is still available below.');
      }
    }

    setMonitoringResidents(residentResult.status === 'fulfilled' ? residentResult.value.data.residents || [] : []);
    setPipelineStatus(statusResult.status === 'fulfilled' ? statusResult.value.data : null);
    setCameras(cameraResult.status === 'fulfilled' ? cameraResult.value.data.cameras || [] : []);
    setPipelineSummary(
      summaryResult.status === 'fulfilled'
        ? Object.values(summaryResult.value.data.summary || {})
        : [],
    );
    setPipelineHistory(historyResult.status === 'fulfilled' ? historyResult.value.data.history || [] : []);

    const hasMonitoringPayload = [residentResult, statusResult, cameraResult, summaryResult, historyResult]
      .some((result) => result.status === 'fulfilled');
    setMonitoringError(hasMonitoringPayload ? '' : 'Monitoring pipeline data is not available right now.');

    if (cameraResult.status === 'fulfilled') {
      const cameraList = cameraResult.value.data.cameras || [];
      if (cameraList.length && !selectedCameraId) {
        setSelectedCameraId(String(cameraList[0].id));
      }
      setSelectedCameraIds((current) => {
        const availableIds = new Set(cameraList.map((camera) => String(camera.id)));
        const filteredCurrent = current.filter((cameraId) => availableIds.has(String(cameraId)));
        if (filteredCurrent.length > 0) {
          return filteredCurrent;
        }
        return cameraList.filter((camera) => camera.detection_ready).map((camera) => String(camera.id));
      });
      if (!cameraList.length) {
        setSelectedCameraId('');
        setSelectedCameraIds([]);
        setCameraDetectionPayload(null);
      }
    }

    setLoading(false);
  };

  useEffect(() => {
    fetchDashboard();
  }, [token]);

  useEffect(() => {
    const loadLocalCameras = async () => {
      if (!navigator.mediaDevices?.enumerateDevices) {
        setLocalCameraError('This browser does not support camera detection.');
        setLocalCameraReady(false);
        return;
      }

      try {
        let permStream = null;
        try {
          permStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        } catch {
          // Permission may be denied; still try enumerateDevices as a fallback.
        }

        const devices = await navigator.mediaDevices.enumerateDevices();
        if (permStream) {
          permStream.getTracks().forEach((track) => track.stop());
        }

        const videoDevices = devices
          .filter((device) => device.kind === 'videoinput')
          .map((device, index) => ({
            id: device.deviceId,
            label: device.label || `PC Camera ${index + 1}`,
          }));

        const finalDevices = videoDevices.length ? videoDevices : [{ id: 'default', label: 'PC Camera 1' }];
        setLocalCameras(finalDevices);
        setSelectedLocalCameraId((currentValue) => currentValue || finalDevices[0]?.id || '');
        setLocalCameraError('');
      } catch (err) {
        setLocalCameraReady(false);
        setLocalCameras([{ id: 'default', label: 'PC Camera 1' }]);
        setSelectedLocalCameraId((currentValue) => currentValue || 'default');
        setLocalCameraError('Unable to detect PC cameras — will use default camera.');
      }
    };

    if (activeOutlogaPage === 'camera') {
      loadLocalCameras();
    } else {
      stopLocalStream();
      setLocalCameraReady(false);
    }

    return () => {
      stopLocalStream();
    };
  }, [activeOutlogaPage]);

  useEffect(() => {
    let isCancelled = false;
    let timerId = null;

    const releasePreviewUrl = () => {
      setLivePreviewUrl((currentUrl) => {
        if (currentUrl) {
          URL.revokeObjectURL(currentUrl);
        }
        return '';
      });
    };

    const fetchLivePreview = async () => {
      try {
        const response = await axios.get(`${API_BASE}/monitoring/live-preview/`, {
          ...authConfig(token),
          responseType: 'blob',
        });

        if (isCancelled) {
          return;
        }

        const nextUrl = URL.createObjectURL(response.data);
        setLivePreviewUrl((currentUrl) => {
          if (currentUrl) {
            URL.revokeObjectURL(currentUrl);
          }
          return nextUrl;
        });
        setLocalCameraReady(true);
      } catch (err) {
        if (err.response?.status === 401) {
          onLogout();
          return;
        }
        if (!isCancelled) {
          if (err.response?.status === 404) {
            setLocalCameraError('');
          }
        }
      } finally {
        if (!isCancelled && activeOutlogaPage === 'camera') {
          timerId = setTimeout(fetchLivePreview, 350);
        }
      }
    };

    if (activeOutlogaPage === 'camera') {
      fetchLivePreview();
    } else {
      releasePreviewUrl();
    }

    return () => {
      isCancelled = true;
      if (timerId) {
        clearTimeout(timerId);
      }
      releasePreviewUrl();
    };
  }, [activeOutlogaPage, token, onLogout]);

  useEffect(() => {
    if (activeOutlogaPage !== 'camera' || !localCameraReady) {
      return;
    }
    attachLocalStreamToVideo();
  }, [activeOutlogaPage, localCameraReady, selectedLocalCameraId]);

  useEffect(() => {
    if (!selectedCameraId) {
      setCameraDetectionPayload(null);
      setCameraDetectionError('');
      return;
    }

    let isCancelled = false;

    const fetchCameraDetections = async () => {
      try {
        const response = await axios.get(
          `${API_BASE}/monitoring/cameras/${selectedCameraId}/detections/`,
          authConfig(token),
        );
        if (!isCancelled) {
          setCameraDetectionPayload(response.data);
          setCameraDetectionError('');
        }
      } catch (err) {
        if (err.response?.status === 401) {
          onLogout();
          return;
        }
        if (!isCancelled) {
          setCameraDetectionError('Unable to fetch live camera detections right now.');
        }
      }
    };

    fetchCameraDetections();
    const intervalId = setInterval(fetchCameraDetections, 5000);

    return () => {
      isCancelled = true;
      clearInterval(intervalId);
    };
  }, [selectedCameraId, token, onLogout]);

  useEffect(() => {
    if (!monitoringResidents.length) {
      setEditResidentKey('');
      setDeleteResidentKey('');
      return;
    }

    const currentEditResident = monitoringResidents.find((resident) => String(resident.id) === String(editResidentKey));
    if (!currentEditResident) {
      const firstResident = monitoringResidents[0];
      setEditResidentKey(String(firstResident.id));
      setEditResidentName(firstResident.name || '');
      setEditResidentCode(firstResident.resident_id ? String(firstResident.resident_id) : '');
    }

    const currentDeleteResident = monitoringResidents.find((resident) => String(resident.id) === String(deleteResidentKey));
    if (!currentDeleteResident) {
      setDeleteResidentKey(String(monitoringResidents[0].id));
    }
  }, [monitoringResidents]);

  const handleEditResidentSelect = (residentId) => {
    setEditResidentKey(residentId);
    const resident = monitoringResidents.find((entry) => String(entry.id) === String(residentId));
    setEditResidentName(resident?.name || '');
    setEditResidentCode(resident?.resident_id ? String(resident.resident_id) : '');
  };

  const handleRunModels = async () => {
    setBusyStartingModels(true);
    setRunModelsMessage('');
    setRunModelsError('');
    try {
      const realCameras = localCameras.filter((cameraItem) => cameraItem.id && cameraItem.id !== 'default');
      const selectedLocalIndex = realCameras.findIndex((cameraItem) => cameraItem.id === selectedLocalCameraId);
      const payload = {
        available_only: false,
        pc_camera_index: selectedLocalIndex >= 0 ? selectedLocalIndex : 0,
      };
      const response = await axios.post(`${API_BASE}/monitoring/start/`, payload, authConfig(token));
      const startedCameras = Array.isArray(response.data?.cameras) ? response.data.cameras : [];
      const localCameraName = localCameras.find((cameraItem) => cameraItem.id === selectedLocalCameraId)?.label;
      const startedCameraName = startedCameras.length
        ? `${startedCameras.length} camera(s)`
        : (localCameraName || response.data?.camera?.name || 'PC camera');
      const skippedCount = Array.isArray(response.data?.skipped_cameras) ? response.data.skipped_cameras.length : 0;
      setRunModelsMessage(
        response.data?.using_machine7_models
          ? `Machine7 models started on ${startedCameraName} using PC camera ${payload.pc_camera_index}.${skippedCount ? ` ${skippedCount} unavailable camera(s) were skipped.` : ''}`
          : `Monitoring started on ${startedCameraName}, but the page is still using compatibility detection.${skippedCount ? ` ${skippedCount} unavailable camera(s) were skipped.` : ''}`
      );
      await fetchDashboard({ keepLoading: true });
    } catch (err) {
      if (err.response?.status === 401) {
        onLogout();
        return;
      }
      if (err.response?.status === 403) {
        setRunModelsError('Access denied. Only Admins and Caregivers can start the detection pipeline.');
      } else if (!err.response) {
        setRunModelsError('Cannot reach the server. Make sure the backend is running and try again.');
      } else {
        setRunModelsError(err.response?.data?.error || err.response?.data?.detail || 'Unable to start models right now.');
      }
    } finally {
      setBusyStartingModels(false);
    }
  };

  const handleCreateCamera = async (event) => {
    event.preventDefault();
    setCameraCreateMessage('');
    setCameraCreateError('');

    if (!newCameraName.trim()) {
      setCameraCreateError('Camera name is required.');
      return;
    }

    try {
      const payload = {
        name: newCameraName.trim(),
        source: newCameraSource.trim(),
        location: newCameraLocation.trim() || 'Unassigned Zone',
        is_active: newCameraActive,
      };
      const response = await axios.post(`${API_BASE}/monitoring/cameras/`, payload, authConfig(token));
      setCameraCreateMessage(response.data?.message || 'Camera created.');
      setNewCameraName('');
      setNewCameraSource('');
      setNewCameraLocation('');
      setNewCameraActive(true);
      await fetchDashboard({ keepLoading: true });
    } catch (err) {
      if (err.response?.status === 401) {
        onLogout();
        return;
      }
      setCameraCreateError(err.response?.data?.error || 'Unable to create the camera right now.');
    }
  };

  const handleStopModels = async () => {
    setBusyStoppingModels(true);
    setRunModelsMessage('');
    setRunModelsError('');
    setGenerateMessage('');
    try {
      const response = await axios.post(`${API_BASE}/monitoring/stop/`, {}, authConfig(token));
      const savedCount = Number(response.data?.saved_detection_summaries || 0);
      setLivePreviewUrl((currentUrl) => {
        if (currentUrl) {
          URL.revokeObjectURL(currentUrl);
        }
        return '';
      });
      setLocalCameraReady(false);

      try {
        const summaryResponse = await axios.get(`${API_BASE}/monitoring/generate-summary/`, authConfig(token));
        const generatedCount = Number(summaryResponse.data?.generated_count || 0);
        if (generatedCount > 0) {
          setGenerateMessage(`Generated ${generatedCount} summary snapshot(s).`);
        } else if (savedCount > 0) {
          setGenerateMessage('Detection stopped. Session was saved, but no summary snapshot was generated.');
        } else {
          setGenerateMessage('Detection stopped, but no mapped resident detections were available to summarize.');
        }
      } catch (summaryErr) {
        if (summaryErr.response?.status === 401) {
          onLogout();
          return;
        }
        setGenerateMessage(summaryErr.response?.data?.error || 'Detection stopped, but summary generation failed.');
      }

      setRunModelsMessage(
        response.data?.stopped
          ? `Detection stopped. Saved ${savedCount} detection session(s).`
          : 'Stop signal sent. Summary requested.'
      );
      await fetchDashboard({ keepLoading: true });
    } catch (err) {
      if (err.response?.status === 401) {
        onLogout();
        return;
      }
      setRunModelsError(err.response?.data?.error || err.response?.data?.detail || 'Unable to stop detection right now.');
    } finally {
      setBusyStoppingModels(false);
    }
  };

  const handleResidentDetection = async () => {
    if (!selectedCameraId) {
      setCameraDetectionError('Select a configured camera to refresh resident detections.');
      return;
    }

    try {
      const response = await axios.get(`${API_BASE}/monitoring/cameras/${selectedCameraId}/detections/`, authConfig(token));
      setCameraDetectionPayload(response.data);
      setCameraDetectionError('');
    } catch (err) {
      if (err.response?.status === 401) {
        onLogout();
        return;
      }
      setCameraDetectionError(err.response?.data?.error || err.response?.data?.detail || 'Unable to refresh resident detections right now.');
    }
  };

  const handleOpenLocalCamera = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setLocalCameraError('This browser does not support local camera access.');
      return;
    }

    try {
      stopLocalStream();

      let stream = null;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: selectedLocalCameraId ? { deviceId: { ideal: selectedLocalCameraId } } : true,
          audio: false,
        });
      } catch (primaryError) {
        // Fallback: try generic camera selection if the chosen device is busy/unavailable.
        stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: false,
        });
      }

      localStreamRef.current = stream;
      await attachLocalStreamToVideo();
      setLocalCameraReady(true);
      setLocalCameraError('');
      return true;
    } catch (err) {
      setLocalCameraReady(false);
      const errorName = err?.name || '';
      if (errorName === 'NotReadableError' || errorName === 'TrackStartError') {
        setLocalCameraError('Preview is unavailable because the camera is currently in use (often by the running model pipeline). Models can still run.');
      } else if (errorName === 'NotAllowedError' || errorName === 'SecurityError') {
        setLocalCameraError('Camera permission was denied. Allow camera access for this website.');
      } else {
        setLocalCameraError('Unable to open the selected PC camera.');
      }
      return false;
    }
  };

  const handleStartCameraAndModels = async () => {
    setLocalCameraError('');
    await handleRunModels();
  };

  const handleEnrollSubmit = async (event) => {
    event.preventDefault();
    setActionMessage('');
    setActionError('');

    if (enrollFiles.length < 5) {
      setActionError('The second-project enrollment flow requires at least 5 images.');
      return;
    }

    const formData = new FormData();
    formData.append('name', enrollName);
    if (enrollResidentId.trim()) {
      formData.append('resident_id', enrollResidentId.trim());
    }
    enrollFiles.forEach((file) => {
      formData.append('images', file);
    });

    try {
      const response = await axios.post(`${API_BASE}/enroll`, formData, authConfig(token));
      setActionMessage(`Enrolled ${response.data.resident.name} with ${response.data.uploaded_images} images.`);
      setEnrollName('');
      setEnrollResidentId('');
      setEnrollFiles([]);
      await fetchDashboard({ keepLoading: true });
    } catch (err) {
      if (err.response?.status === 401) {
        onLogout();
        return;
      }
      setActionError(err.response?.data?.error || 'Unable to enroll the resident right now.');
    }
  };

  const handleEditSubmit = async (event) => {
    event.preventDefault();
    setActionMessage('');
    setActionError('');
    if (!editResidentKey) {
      setActionError('Select a resident to update.');
      return;
    }

    try {
      const payload = {
        name: editResidentName,
        resident_id: editResidentCode.trim() ? Number(editResidentCode.trim()) : undefined,
      };

      try {
        await axios.post(`${API_BASE}/residents/${editResidentKey}/update`, payload, authConfig(token));
      } catch (postErr) {
        // Fallback for servers that only expose PATCH on the base resident endpoint.
        await axios.patch(`${API_BASE}/residents/${editResidentKey}`, payload, authConfig(token));
      }

      setActionMessage('Resident profile updated.');
      await fetchDashboard({ keepLoading: true });
    } catch (err) {
      if (err.response?.status === 401) {
        onLogout();
        return;
      }
      setActionError(err.response?.data?.error || err.response?.data?.detail || 'Unable to update the resident right now.');
    }
  };

  const handleDeleteSubmit = async (event) => {
    event.preventDefault();
    setActionMessage('');
    setActionError('');
    if (!deleteResidentKey) {
      setActionError('Select a resident to delete.');
      return;
    }

    try {
      try {
        await axios.post(`${API_BASE}/residents/${deleteResidentKey}/delete`, {}, authConfig(token));
      } catch (postErr) {
        // Fallback for servers that only expose DELETE on the base resident endpoint.
        await axios.delete(`${API_BASE}/residents/${deleteResidentKey}`, authConfig(token));
      }

      setActionMessage('Resident deleted from the monitoring roster.');
      await fetchDashboard({ keepLoading: true });
    } catch (err) {
      if (err.response?.status === 401) {
        onLogout();
        return;
      }
      setActionError(err.response?.data?.error || err.response?.data?.detail || 'Unable to delete the resident right now.');
    }
  };

  if (loading) {
    return <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--midnight-green)' }}><h2>Loading Staff Dashboard...</h2></div>;
  }

  const hasAnyDashboardData = residents.length || monitoringResidents.length || cameras.length || pipelineHistory.length || pipelineSummary.length;
  const liveCameras = cameras.filter((cameraItem) => cameraItem.is_live).length;
  const selectedCamera = cameras.find((cameraItem) => String(cameraItem.id) === String(selectedCameraId));
  const selectedCameraSourceType = getCameraSourceType(selectedCamera?.source);
  const detectionModeLabel = cameraDetectionPayload?.using_machine7_models ? 'True Machine7 detection' : 'Compatibility detection';
  const detectionModeColor = cameraDetectionPayload?.using_machine7_models ? '#0F766E' : '#B45309';
  const isTrueDetectionRunning = Boolean(cameraDetectionPayload?.true_detection_running);

  return (
    <div style={shellStyle}>
      <aside style={sidebarStyle}>
        <div style={{ padding: '1.5rem 2rem', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
          <Link to="/dashboard"><img src="/LOGO_AURACARE.png" alt="AuraCare Logo" style={{ height: '40px' }} /></Link>
        </div>
        <nav style={{ flex: 1, padding: '1rem' }}>
          <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', listStyle: 'none', padding: 0 }}>
            <li>
              <button
                onClick={() => navigate('/dashboard')}
                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', width: '100%', textAlign: 'left', backgroundColor: !isLogActivitiesRoute ? 'rgba(255,255,255,0.1)' : 'transparent', borderRadius: 'var(--border-radius-sm)', color: !isLogActivitiesRoute ? 'var(--moonstone)' : 'rgba(255,255,255,0.75)' }}
              >
                <Users size={18} /> Dashboard
              </button>
            </li>
            <li>
              <button
                onClick={() => navigate('/dashboard/log-activities')}
                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', width: '100%', textAlign: 'left', backgroundColor: isLogActivitiesRoute ? 'rgba(255,255,255,0.1)' : 'transparent', borderRadius: 'var(--border-radius-sm)', color: isLogActivitiesRoute ? 'var(--moonstone)' : 'rgba(255,255,255,0.75)' }}
              >
                <Radar size={18} /> Log Activities
              </button>
            </li>
          </ul>
        </nav>
        <div style={{ padding: '2rem' }}>
          <button onClick={onLogout} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'rgba(255,255,255,0.7)', width: '100%', background: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem' }}>
            <LogOut size={18} /> Sign Out
          </button>
        </div>
      </aside>

      <main style={{ flex: 1, padding: '3rem' }}>
          <>
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '2rem', marginBottom: '2rem' }}>
              <div>
                <h1 style={{ color: 'var(--midnight-green)', margin: 0 }}>
                  {isLogActivitiesRoute ? 'Oultlog Activities' : 'Caregiver Dashboard'}
                </h1>
                <p style={{ color: 'var(--text-light)', margin: '0.35rem 0 0 0' }}>
                  {isLogActivitiesRoute
                    ? 'Standalone activity workspace: Resident Entry, Camera Detection, and Summary Generation.'
                    : 'Original AuraCare overview with the monitoring pipeline from the second project.'}
                </p>
              </div>
            </header>

            {!isLogActivitiesRoute && !hasMonitoringResidents ? (
              <div style={{ ...subtlePanelStyle, marginBottom: '1.5rem', display: 'grid', gridTemplateColumns: '1.3fr 1fr', gap: '1.5rem', alignItems: 'center' }}>
                <div>
                  <h2 style={{ color: 'var(--midnight-green)', marginTop: 0, marginBottom: '0.5rem' }}>Resident roster cleared</h2>
                  <p style={{ color: 'var(--text-light)', margin: 0 }}>There are no residents in the system right now. Use the enrollment panel below to add people back with the second-project image flow.</p>
                </div>
                <div style={{ backgroundColor: 'white', borderRadius: '16px', padding: '1rem 1.2rem' }}>
                  <p style={{ margin: '0 0 0.4rem 0', color: 'var(--midnight-green)', fontWeight: 'bold' }}>Quick start</p>
                  <p style={{ margin: '0 0 0.25rem 0', color: 'var(--text-light)', fontSize: '0.9rem' }}>1. Enter a resident name</p>
                  <p style={{ margin: '0 0 0.25rem 0', color: 'var(--text-light)', fontSize: '0.9rem' }}>2. Attach at least 5 images</p>
                  <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.9rem' }}>3. Submit the enrollment form</p>
                </div>
              </div>
            ) : null}

            {!isLogActivitiesRoute && generateMessage ? (
              <div style={{ ...panelStyle, marginBottom: '1.5rem', backgroundColor: '#F0FDFA', color: 'var(--midnight-green)' }}>
                {generateMessage}
              </div>
            ) : null}

            {!isLogActivitiesRoute && staffErrorMsg ? (
              <div style={{ ...panelStyle, marginBottom: '1.5rem', backgroundColor: '#FFF7ED' }}>
                <p style={{ margin: 0, color: '#9A3412' }}>{staffErrorMsg}</p>
              </div>
            ) : null}

            {!isLogActivitiesRoute && monitoringError ? (
              <div style={{ ...panelStyle, marginBottom: '1.5rem', backgroundColor: '#FEF2F2' }}>
                <p style={{ margin: 0, color: '#B91C1C' }}>{monitoringError}</p>
              </div>
            ) : null}

            {!isLogActivitiesRoute && !hasAnyDashboardData && (staffErrorMsg || monitoringError) ? (
              <div style={{ ...panelStyle, textAlign: 'center', padding: '2rem', marginBottom: '1.5rem' }}>
                <AlertCircle size={40} color="var(--moonstone)" style={{ marginBottom: '0.75rem' }} />
                <h2 style={{ color: 'var(--midnight-green)', marginBottom: '0.6rem' }}>Limited Data</h2>
                <p style={{ color: 'var(--text-light)', fontSize: '1rem' }}>{monitoringError || staffErrorMsg}</p>
              </div>
            ) : null}

            {!isLogActivitiesRoute ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
                <MetricCard title="Assigned Residents" value={residents.length} subtitle="Original AuraCare cards" accent="var(--midnight-green)" />
                <MetricCard title="Monitoring Residents" value={monitoringResidents.length} subtitle="Second-project compatibility" accent="var(--moonstone)" />
                <MetricCard title="Live Cameras" value={liveCameras} subtitle={`${cameras.length} camera records`} accent="#0F766E" />
                <MetricCard title="Recent Sessions" value={pipelineHistory.length} subtitle="Pipeline activity history" accent="#B45309" />
              </div>
            ) : null}

            {!isLogActivitiesRoute ? (
              <section style={{ marginBottom: '2rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1rem' }}>
                  <Users size={20} color="var(--midnight-green)" />
                  <h2 style={{ color: 'var(--midnight-green)', margin: 0 }}>Assigned Residents</h2>
                </div>
                {residents.length > 0 ? (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1.5rem' }}>
                    {residents.map((resident) => (
                      <div key={resident.id} style={{ ...panelStyle, borderTop: `4px solid ${resident.risk_level === 'HIGH' ? '#EF4444' : resident.risk_level === 'MEDIUM' ? '#F59E0B' : 'var(--moonstone)'}` }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                          <div>
                            <h3 style={{ margin: 0, color: 'var(--midnight-green)' }}>{resident.name}</h3>
                            <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.9rem' }}>Room: {resident.room_number} | Age: {resident.age}</p>
                          </div>
                          <span style={{ fontSize: '0.8rem', fontWeight: 'bold', padding: '4px 8px', borderRadius: '12px', backgroundColor: resident.risk_level === 'HIGH' ? '#FEE2E2' : resident.risk_level === 'MEDIUM' ? '#FEF3C7' : '#E0F2FE', color: resident.risk_level === 'HIGH' ? '#B91C1C' : resident.risk_level === 'MEDIUM' ? '#B45309' : '#0369A1' }}>
                            {resident.risk_level} RISK
                          </span>
                        </div>
                        <div style={{ padding: '1rem', backgroundColor: 'var(--alice-blue)', borderRadius: 'var(--border-radius-sm)', marginBottom: '1rem' }}>
                          <p style={{ margin: 0, fontWeight: 'bold', color: 'var(--midnight-green)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <HeartPulse size={16} color="var(--moonstone)" /> Recent Metrics
                          </p>
                          <ul style={{ listStyle: 'none', padding: 0, margin: '0.5rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-dark)' }}>
                            {resident.metrics && resident.metrics.length > 0 ? resident.metrics.slice(0, 3).map((metric, idx) => (
                              <li key={idx} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                                <span>{metric.metric_type_display}</span>
                                <span style={{ fontWeight: 'bold' }}>{metric.value}</span>
                              </li>
                            )) : <li>No recent metrics.</li>}
                          </ul>
                        </div>
                        <div>
                          <p style={{ margin: 0, fontWeight: 'bold', color: '#EF4444', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <AlertCircle size={16} /> Recent Incidents
                          </p>
                          <ul style={{ listStyle: 'none', padding: 0, margin: '0.5rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-dark)' }}>
                            {resident.incidents && resident.incidents.length > 0 ? resident.incidents.slice(0, 2).map((incident, idx) => (
                              <li key={idx} style={{ padding: '0.5rem', backgroundColor: '#FEE2E2', borderRadius: '4px', marginBottom: '0.3rem' }}>
                                <strong>{incident.type_display}</strong> in {incident.zone?.name || 'Unknown'}
                              </li>
                            )) : <li style={{ color: 'var(--text-light)' }}>No recent incidents.</li>}
                          </ul>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyPanel
                    title="No assigned residents"
                    message="The original AuraCare assignment view is empty right now."
                    detail="You can still use the monitoring sections below to set residents back up."
                  />
                )}
              </section>
            ) : null}

            {isLogActivitiesRoute ? (
            <section style={{ marginBottom: '2rem' }}>
              <div style={{ ...panelStyle, padding: '1.2rem' }}>
                <div style={{ display: 'grid', justifyItems: 'center', gap: '0.9rem', marginBottom: '0.9rem' }}>
                  <h2 style={{ color: 'var(--midnight-green)', margin: 0 }}>Oultlog Activities</h2>
                  <div style={{ display: 'flex', justifyContent: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                    <button
                      onClick={() => navigate('/dashboard/log-activities/resident-entry')}
                      style={{ ...tabButtonStyle, backgroundColor: activeOutlogaPage === 'entry' ? 'var(--midnight-green)' : 'white', color: activeOutlogaPage === 'entry' ? 'white' : 'var(--midnight-green)' }}
                    >
                      Resident Entry
                    </button>
                    <button
                      onClick={() => navigate('/dashboard/log-activities/camera-detection')}
                      style={{ ...tabButtonStyle, backgroundColor: activeOutlogaPage === 'camera' ? 'var(--midnight-green)' : 'white', color: activeOutlogaPage === 'camera' ? 'white' : 'var(--midnight-green)' }}
                    >
                      Camera Detection
                    </button>
                    <button
                      onClick={() => navigate('/dashboard/log-activities/summary-generation')}
                      style={{ ...tabButtonStyle, backgroundColor: activeOutlogaPage === 'summary' ? 'var(--midnight-green)' : 'white', color: activeOutlogaPage === 'summary' ? 'white' : 'var(--midnight-green)' }}
                    >
                      Summary
                    </button>
                  </div>
                </div>

                {actionMessage ? (
                  <div style={{ ...panelStyle, marginBottom: '1rem', backgroundColor: '#ECFDF5', color: '#065F46' }}>{actionMessage}</div>
                ) : null}
                {actionError ? (
                  <div style={{ ...panelStyle, marginBottom: '1rem', backgroundColor: '#FEF2F2', color: '#B91C1C' }}>{actionError}</div>
                ) : null}

                {activeOutlogaPage === 'entry' ? (
                  <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '1.5rem' }}>
                    <div style={{ display: 'grid', gap: '1rem' }}>
                      <form onSubmit={handleEnrollSubmit} style={panelStyle}>
                        <h3 style={{ marginTop: 0, color: 'var(--midnight-green)' }}>Resident Entry</h3>
                        <p style={{ color: 'var(--text-light)', marginTop: 0 }}>Create resident entry with second-project enrollment images.</p>
                        <div style={{ display: 'grid', gap: '0.9rem' }}>
                          <label style={{ display: 'grid', gap: '0.4rem', color: 'var(--midnight-green)', fontSize: '0.9rem', fontWeight: 'bold' }}>
                            Resident name
                            <input
                              style={inputStyle}
                              value={enrollName}
                              onChange={(event) => setEnrollName(event.target.value)}
                              placeholder="Resident name"
                              required
                            />
                          </label>
                          <label style={{ display: 'grid', gap: '0.4rem', color: 'var(--midnight-green)', fontSize: '0.9rem', fontWeight: 'bold' }}>
                            Resident ID
                            <input
                              style={inputStyle}
                              value={enrollResidentId}
                              onChange={(event) => setEnrollResidentId(event.target.value)}
                              placeholder="Resident ID (optional)"
                            />
                          </label>
                          <label style={{ display: 'grid', gap: '0.4rem', color: 'var(--midnight-green)', fontSize: '0.9rem', fontWeight: 'bold' }}>
                            Enrollment images
                            <input
                              style={inputStyle}
                              type="file"
                              accept="image/*"
                              multiple
                              onChange={(event) => setEnrollFiles(Array.from(event.target.files || []))}
                            />
                          </label>
                          <p style={{ margin: 0, color: enrollFiles.length >= 5 ? '#0F766E' : 'var(--text-light)', fontSize: '0.85rem' }}>{enrollFiles.length} image(s) selected. Minimum required: 5.</p>
                          <button type="submit" style={{ ...actionButtonStyle, backgroundColor: 'var(--moonstone)', color: 'white' }}>
                            Save Resident Entry
                          </button>
                        </div>
                      </form>

                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                        <form onSubmit={handleEditSubmit} style={panelStyle}>
                          <h3 style={{ marginTop: 0, color: 'var(--midnight-green)' }}>Edit Resident</h3>
                          <div style={{ display: 'grid', gap: '0.9rem' }}>
                            <select
                              style={inputStyle}
                              value={editResidentKey}
                              onChange={(event) => handleEditResidentSelect(event.target.value)}
                              disabled={!hasMonitoringResidents}
                            >
                              {!hasMonitoringResidents ? <option value="">No residents available</option> : null}
                              {monitoringResidents.map((resident) => (
                                <option key={resident.id} value={resident.id}>{resident.name}</option>
                              ))}
                            </select>
                            <input
                              style={inputStyle}
                              value={editResidentName}
                              onChange={(event) => setEditResidentName(event.target.value)}
                              placeholder="Resident name"
                              required
                              disabled={!hasMonitoringResidents}
                            />
                            <input
                              style={inputStyle}
                              value={editResidentCode}
                              onChange={(event) => setEditResidentCode(event.target.value)}
                              placeholder="Resident ID"
                              disabled={!hasMonitoringResidents}
                            />
                            <button type="submit" disabled={!hasMonitoringResidents} style={{ ...actionButtonStyle, backgroundColor: 'var(--midnight-green)', color: 'white', opacity: hasMonitoringResidents ? 1 : 0.5, cursor: hasMonitoringResidents ? 'pointer' : 'not-allowed' }}>
                              Save Changes
                            </button>
                          </div>
                        </form>

                        <form onSubmit={handleDeleteSubmit} style={panelStyle}>
                          <h3 style={{ marginTop: 0, color: 'var(--midnight-green)' }}>Delete Resident</h3>
                          <div style={{ display: 'grid', gap: '0.9rem' }}>
                            <select
                              style={inputStyle}
                              value={deleteResidentKey}
                              onChange={(event) => setDeleteResidentKey(event.target.value)}
                              disabled={!hasMonitoringResidents}
                            >
                              {!hasMonitoringResidents ? <option value="">No residents available</option> : null}
                              {monitoringResidents.map((resident) => (
                                <option key={resident.id} value={resident.id}>{resident.name}</option>
                              ))}
                            </select>
                            <button type="submit" disabled={!hasMonitoringResidents} style={{ ...actionButtonStyle, backgroundColor: '#B91C1C', color: 'white', opacity: hasMonitoringResidents ? 1 : 0.5, cursor: hasMonitoringResidents ? 'pointer' : 'not-allowed' }}>
                              Delete Resident
                            </button>
                          </div>
                        </form>
                      </div>
                    </div>

                    <div style={panelStyle}>
                      <h3 style={{ marginTop: 0, color: 'var(--midnight-green)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <ShieldAlert size={18} /> Resident Roster
                      </h3>
                      {monitoringResidents.length > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '640px', overflowY: 'auto', paddingRight: '0.25rem' }}>
                          {monitoringResidents.map((resident) => (
                            <div key={resident.id} style={{ padding: '0.9rem', backgroundColor: 'var(--alice-blue)', borderRadius: '12px' }}>
                              <p style={{ margin: '0 0 0.2rem 0', fontWeight: 'bold', color: 'var(--midnight-green)' }}>{resident.name}</p>
                              <p style={{ margin: '0 0 0.2rem 0', color: 'var(--text-light)', fontSize: '0.88rem' }}>Resident ID: {resident.resident_id || 'Auto'}</p>
                              <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.88rem' }}>Enrollment images: {resident.image_count}</p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <EmptyPanel
                          title="No monitoring residents"
                          message="Create your first resident entry to start camera detection."
                        />
                      )}
                    </div>
                  </div>
                ) : null}

                {activeOutlogaPage === 'camera' ? (
                  <div style={{ display: 'grid', gap: '1rem' }}>
                    {runModelsMessage ? (
                      <div style={{ ...panelStyle, backgroundColor: '#ECFDF5', color: '#065F46' }}>
                        {runModelsMessage}
                      </div>
                    ) : null}
                    {runModelsError ? (
                      <div style={{ ...panelStyle, backgroundColor: '#FEF2F2', color: '#B91C1C' }}>
                        {runModelsError}
                      </div>
                    ) : null}
                    {cameraDetectionError ? (
                      <div style={{ ...panelStyle, backgroundColor: '#FEF2F2' }}>
                        <p style={{ margin: 0, color: '#B91C1C' }}>{cameraDetectionError}</p>
                      </div>
                    ) : null}
                    {localCameraError ? (
                      <div style={{ ...panelStyle, backgroundColor: '#FEF2F2' }}>
                        <p style={{ margin: 0, color: '#B91C1C' }}>{localCameraError}</p>
                      </div>
                    ) : null}

                    <div style={panelStyle}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap' }}>
                        <h3 style={{ color: 'var(--midnight-green)', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <Camera size={18} /> Live Camera Screen
                        </h3>
                        <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center', flexWrap: 'wrap' }}>
                          <select
                            style={{ ...inputStyle, width: 'min(360px, 100%)' }}
                            value={selectedLocalCameraId}
                            onChange={(event) => setSelectedLocalCameraId(event.target.value)}
                            disabled={!localCameras.length}
                          >
                            {!localCameras.length ? <option value="">No PC camera available</option> : null}
                            {localCameras.map((cameraItem) => (
                              <option key={cameraItem.id} value={cameraItem.id}>{cameraItem.label}</option>
                            ))}
                          </select>
                        </div>
                      </div>

                      <div style={{ ...subtlePanelStyle, padding: '1.25rem', marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1.5rem', flexWrap: 'wrap' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem', flex: 1 }}>
                          <div>
                            <p style={{ margin: '0 0 0.2rem 0', color: 'var(--text-light)', fontSize: '0.82rem' }}>Location</p>
                            <p style={{ margin: 0, color: 'var(--midnight-green)', fontWeight: 'bold', fontSize: '0.95rem' }}>
                              {selectedCamera?.location || (localCameras.find((c) => c.id === selectedLocalCameraId)?.label ? 'PC Camera' : 'No camera selected')}
                            </p>
                          </div>
                          <div>
                            <p style={{ margin: '0 0 0.2rem 0', color: 'var(--text-light)', fontSize: '0.82rem' }}>Status</p>
                            <p style={{ margin: 0, fontWeight: 'bold', fontSize: '0.95rem', color: selectedCamera ? (selectedCamera.is_active ? '#0F766E' : '#B45309') : (localCameras.length ? '#0F766E' : '#B45309') }}>
                              {selectedCamera ? (selectedCamera.is_active ? 'Active' : 'Inactive') : (localCameras.length ? 'PC Camera Available' : 'No Camera Detected')}
                            </p>
                          </div>
                          <div>
                            <p style={{ margin: '0 0 0.2rem 0', color: 'var(--text-light)', fontSize: '0.82rem' }}>PC Cameras</p>
                            <p style={{ margin: 0, color: 'var(--midnight-green)', fontWeight: 'bold', fontSize: '0.95rem' }}>
                              {localCameras.length ? `${localCameras.length} device(s) detected` : 'None detected'}
                            </p>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={handleStartCameraAndModels}
                          disabled={busyStartingModels || busyStoppingModels}
                          style={{ border: 'none', borderRadius: '14px', padding: '1rem 2rem', fontWeight: 'bold', fontSize: '1rem', cursor: busyStartingModels || busyStoppingModels ? 'not-allowed' : 'pointer', backgroundColor: 'var(--midnight-green)', color: 'white', opacity: busyStartingModels || busyStoppingModels ? 0.5 : 1, whiteSpace: 'nowrap', boxShadow: '0 4px 16px rgba(4,28,36,0.2)', letterSpacing: '0.01em' }}
                        >
                          {busyStartingModels ? '⏳ Starting...' : '▶ Start Models (PC + Website)'}
                        </button>
                        <button
                          type="button"
                          onClick={handleStopModels}
                          disabled={busyStoppingModels}
                          style={{ border: 'none', borderRadius: '14px', padding: '1rem 1.4rem', fontWeight: 'bold', fontSize: '1rem', cursor: busyStoppingModels ? 'not-allowed' : 'pointer', backgroundColor: '#B91C1C', color: 'white', opacity: busyStoppingModels ? 0.55 : 1, whiteSpace: 'nowrap', boxShadow: '0 4px 16px rgba(4,28,36,0.2)', letterSpacing: '0.01em' }}
                        >
                          {busyStoppingModels ? '⏳ Stopping + Summary...' : '■ Stop + Get Summary'}
                        </button>
                      </div>

                      {!localCameras.length ? (
                        <EmptyPanel title="No camera selected" message="Connect a PC camera to start detection models." />
                      ) : (
                        <div style={{ display: 'grid', gap: '1rem' }}>
                          <div style={{ width: '100%', minHeight: '260px', borderRadius: '14px', backgroundColor: '#041C24', color: '#D1ECF2', padding: '0.75rem', display: 'grid', placeItems: 'center', border: '1px solid rgba(68,166,181,0.35)' }}>
                            <div style={{ textAlign: 'center', width: '100%' }}>
                              <p style={{ margin: 0, fontWeight: 'bold', color: '#93DCE7' }}>
                                {localCameras.length ? (localCameras.find((cameraItem) => cameraItem.id === selectedLocalCameraId)?.label || 'This PC Camera') : (selectedCamera?.name || 'Selected camera')}
                              </p>
                              <p style={{ margin: '0.45rem 0 1rem 0', fontSize: '0.88rem', color: '#9FBCC2' }}>
                                {localCameras.length ? 'Same pipeline video is shown in Python window and mirrored in website' : 'Live detection screen for second-project models'}
                              </p>
                              {localCameras.length ? (
                                <div style={{ display: 'grid', gap: '0.75rem', maxWidth: '720px', margin: '0 auto' }}>
                                  <div style={{ width: '100%', aspectRatio: '16 / 9', borderRadius: '12px', overflow: 'hidden', border: '1px solid rgba(147,220,231,0.35)', backgroundColor: '#021219' }}>
                                    {livePreviewUrl ? (
                                      <img
                                        src={livePreviewUrl}
                                        alt="Live pipeline preview"
                                        style={{ width: '100%', height: '100%', objectFit: 'cover', backgroundColor: '#021219' }}
                                      />
                                    ) : (
                                      <div style={{ width: '100%', height: '100%', backgroundColor: '#000' }} />
                                    )}
                                  </div>
                                  <p style={{ margin: 0, color: '#9FBCC2', fontSize: '0.85rem' }}>
                                    Model output window stays on PC, and this page mirrors the same frames.
                                  </p>
                                </div>
                              ) : selectedCamera?.source ? (
                                <div style={{ display: 'grid', gap: '0.75rem' }}>
                                  <div style={{ width: '100%', aspectRatio: '16 / 9', borderRadius: '12px', overflow: 'hidden', border: '1px solid rgba(147,220,231,0.3)' }}>
                                    {selectedCameraSourceType === 'mjpeg' ? (
                                      <img
                                        src={selectedCamera.source}
                                        alt={selectedCamera.name}
                                        style={{ width: '100%', height: '100%', objectFit: 'cover', backgroundColor: '#021219' }}
                                      />
                                    ) : null}
                                    {selectedCameraSourceType === 'video' || selectedCameraSourceType === 'hls' ? (
                                      <video
                                        src={selectedCamera.source}
                                        autoPlay
                                        muted
                                        controls
                                        playsInline
                                        style={{ width: '100%', height: '100%', objectFit: 'cover', backgroundColor: '#021219' }}
                                      />
                                    ) : null}
                                    {selectedCameraSourceType === 'web' || selectedCameraSourceType === 'unknown' ? (
                                      <iframe
                                        title={`camera-${selectedCamera.id}`}
                                        src={selectedCamera.source}
                                        style={{ width: '100%', height: '100%', border: 0, backgroundColor: '#021219' }}
                                        allow="autoplay; camera"
                                      />
                                    ) : null}
                                    {selectedCameraSourceType === 'rtsp' ? (
                                      <div style={{ display: 'grid', placeItems: 'center', width: '100%', height: '100%', padding: '1rem', textAlign: 'center', backgroundColor: '#021219' }}>
                                        <p style={{ margin: 0, color: '#9FBCC2', fontSize: '0.9rem' }}>
                                          RTSP feeds cannot render directly in most browsers. Use the Open Camera Feed button or configure an HTTP/HLS camera stream URL.
                                        </p>
                                      </div>
                                    ) : null}
                                  </div>
                                  <p style={{ margin: 0, fontSize: '0.85rem', color: '#9FBCC2', wordBreak: 'break-all' }}>
                                    Source: {selectedCamera.source}
                                  </p>
                                </div>
                              ) : (
                                <p style={{ margin: 0, fontSize: '0.9rem', color: '#9FBCC2' }}>
                                  No local PC camera preview or configured stream is available right now.
                                </p>
                              )}
                            </div>
                          </div>

                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '0.9rem' }}>
                            <div style={{ ...subtlePanelStyle, padding: '1rem' }}>
                              <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.85rem' }}>Detection mode</p>
                              <p style={{ margin: '0.25rem 0 0 0', color: detectionModeColor, fontWeight: 'bold' }}>{detectionModeLabel}</p>
                            </div>
                            <div style={{ ...subtlePanelStyle, padding: '1rem' }}>
                              <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.85rem' }}>Resident detections</p>
                              <p style={{ margin: '0.25rem 0 0 0', color: 'var(--midnight-green)', fontWeight: 'bold' }}>{cameraDetectionPayload?.resident_detections?.length || 0}</p>
                            </div>
                            <div style={{ ...subtlePanelStyle, padding: '1rem' }}>
                              <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.85rem' }}>Recent events</p>
                              <p style={{ margin: '0.25rem 0 0 0', color: 'var(--midnight-green)', fontWeight: 'bold' }}>{cameraDetectionPayload?.recent_camera_events?.length || 0}</p>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>

                    <div style={panelStyle}>
                      <h3 style={{ color: 'var(--midnight-green)', marginTop: 0, marginBottom: '0.8rem' }}>Live Detection Info</h3>
                      <div style={{ ...subtlePanelStyle, padding: '0.9rem', marginBottom: '1rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
                        <div>
                          <p style={{ margin: '0 0 0.2rem 0', color: 'var(--text-light)', fontSize: '0.82rem' }}>Selected camera</p>
                          <p style={{ margin: 0, color: 'var(--midnight-green)', fontWeight: 'bold' }}>
                            {localCameras.length
                              ? `PC Camera: ${localCameras.find((cameraItem) => cameraItem.id === selectedLocalCameraId)?.label || 'This PC Camera'}`
                              : (cameraDetectionPayload?.camera?.name || selectedCamera?.name || 'No camera selected')}
                          </p>
                        </div>
                        <div>
                          <p style={{ margin: '0 0 0.2rem 0', color: 'var(--text-light)', fontSize: '0.82rem' }}>Location</p>
                          <p style={{ margin: 0, color: 'var(--text-dark)', fontSize: '0.9rem' }}>
                            {localCameras.length
                              ? 'Local PC camera'
                              : (cameraDetectionPayload?.camera?.location || selectedCamera?.location || 'Unknown location')}
                          </p>
                        </div>
                        <div>
                          <p style={{ margin: '0 0 0.2rem 0', color: 'var(--text-light)', fontSize: '0.82rem' }}>Detection status</p>
                          <p style={{ margin: 0, color: isTrueDetectionRunning ? '#0F766E' : '#B45309', fontWeight: 'bold', fontSize: '0.9rem' }}>
                            {isTrueDetectionRunning
                              ? (localCameras.length ? 'Active (PC camera)' : 'Active')
                              : (localCameras.length ? 'PC camera selected - not active yet' : 'Not active yet')}
                          </p>
                        </div>
                        {cameraDetectionPayload?.machine7_error ? (
                          <div style={{ gridColumn: '1 / -1' }}>
                            <p style={{ margin: 0, color: '#B91C1C', fontSize: '0.85rem' }}>{cameraDetectionPayload.machine7_error}</p>
                          </div>
                        ) : null}
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                        <div>
                          <p style={{ margin: '0 0 0.6rem 0', color: 'var(--midnight-green)', fontWeight: 'bold', fontSize: '0.9rem' }}>Resident Detections</p>
                          {cameraDetectionPayload?.resident_detections?.length ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '320px', overflowY: 'auto', paddingRight: '0.25rem' }}>
                              {cameraDetectionPayload.resident_detections.map((detection) => (
                                <div key={`${detection.person_id}-${detection.last_seen}`} style={{ padding: '0.9rem', backgroundColor: 'var(--alice-blue)', borderRadius: '12px' }}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', alignItems: 'flex-start' }}>
                                    <p style={{ margin: '0 0 0.25rem 0', fontWeight: 'bold', color: 'var(--midnight-green)' }}>{detection.name}</p>
                                    <span style={{ fontSize: '0.75rem', fontWeight: 'bold', padding: '4px 8px', borderRadius: '999px', backgroundColor: detection.detection_source === 'machine7' ? '#DCFCE7' : '#FEF3C7', color: detection.detection_source === 'machine7' ? '#166534' : '#92400E' }}>
                                      {detection.detection_source === 'machine7' ? 'True detection' : 'Compatibility'}
                                    </span>
                                  </div>
                                  <p style={{ margin: '0 0 0.2rem 0', color: 'var(--text-dark)', fontSize: '0.9rem' }}>Detected at: {detection.detected_location || detection.camera_location || detection.area || 'Unknown location'}</p>
                                  <p style={{ margin: '0 0 0.2rem 0', color: 'var(--text-dark)', fontSize: '0.9rem' }}>Activity: {detection.activity}</p>
                                  <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.85rem' }}>Last seen: {formatTimestamp(detection.last_seen)}</p>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <EmptyPanel
                              title="No detections yet"
                              message={cameraDetectionPayload?.using_machine7_models ? 'Pipeline active — no resident detected yet.' : 'Waiting for detections.'}
                            />
                          )}
                        </div>

                        <div>
                          <p style={{ margin: '0 0 0.6rem 0', color: 'var(--midnight-green)', fontWeight: 'bold', fontSize: '0.9rem' }}>Recent Camera Events</p>
                          {cameraDetectionPayload?.recent_camera_events?.length ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '320px', overflowY: 'auto', paddingRight: '0.25rem' }}>
                              {cameraDetectionPayload.recent_camera_events.map((eventItem, idx) => (
                                <div key={`${eventItem.created_at || idx}-${idx}`} style={{ padding: '0.9rem', borderLeft: '4px solid var(--moonstone)', backgroundColor: 'var(--alice-blue)', borderRadius: '0 12px 12px 0' }}>
                                  <p style={{ margin: '0 0 0.25rem 0', fontWeight: 'bold', color: 'var(--midnight-green)' }}>{eventItem.resident}</p>
                                  <p style={{ margin: '0 0 0.2rem 0', color: 'var(--text-dark)', fontSize: '0.9rem' }}>{eventItem.summary_text || 'No summary text provided.'}</p>
                                  <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.85rem' }}>{eventItem.location} | {formatTimestamp(eventItem.created_at)}</p>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <EmptyPanel
                              title="No camera events yet"
                              message="Events will appear here while monitoring is running."
                            />
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : null}

                {activeOutlogaPage === 'summary' ? (
                  <div style={{ display: 'grid', gap: '1rem' }}>
                    <div style={{ ...panelStyle }}>
                      <div>
                        <h3 style={{ color: 'var(--midnight-green)', margin: 0 }}>Generated Summaries</h3>
                        <p style={{ color: 'var(--text-light)', margin: '0.25rem 0 0 0' }}>
                          Review generated summaries.
                        </p>
                      </div>
                    </div>

                    {generateMessage ? (
                      <div style={{ ...panelStyle, backgroundColor: '#F0FDFA', color: 'var(--midnight-green)' }}>
                        {generateMessage}
                      </div>
                    ) : null}

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                      <div style={panelStyle}>
                        <h3 style={{ color: 'var(--midnight-green)', marginTop: 0, marginBottom: '0.8rem' }}>Summary Snapshots</h3>
                        {pipelineSummary.length > 0 ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '500px', overflowY: 'auto', paddingRight: '0.25rem' }}>
                            {pipelineSummary.map((item) => (
                              <div key={item.person_id} style={{ padding: '1rem', backgroundColor: 'var(--alice-blue)', borderRadius: 'var(--border-radius-sm)' }}>
                                <strong style={{ color: 'var(--midnight-green)' }}>{item.name}</strong>
                                <p style={{ margin: '0.35rem 0', color: 'var(--text-dark)' }}>{item.summary_line}</p>
                                <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.85rem' }}>
                                  Top area: {item.top_area || 'N/A'}
                                </p>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <EmptyPanel
                            title="No monitoring summaries"
                            message="Start and stop detection to populate this page with summaries."
                          />
                        )}
                      </div>

                      <div style={panelStyle}>
                        <h3 style={{ color: 'var(--midnight-green)', marginTop: 0, marginBottom: '0.8rem' }}>All Generated History</h3>
                        {pipelineHistory.length > 0 ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '500px', overflowY: 'auto', paddingRight: '0.25rem' }}>
                            {pipelineHistory.map((entry) => (
                              <div key={entry.id} style={{ padding: '1rem', borderLeft: '4px solid var(--moonstone)', backgroundColor: 'var(--alice-blue)', borderRadius: '0 var(--border-radius-sm) var(--border-radius-sm) 0' }}>
                                <p style={{ margin: '0 0 0.35rem 0', fontWeight: 'bold', color: 'var(--midnight-green)' }}>{entry.name}</p>
                                <p style={{ margin: '0 0 0.25rem 0', color: 'var(--text-dark)' }}>{formatHistoryEntry(entry)}</p>
                                <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.85rem' }}>Top area: {entry.location} | {formatTimestamp(entry.created_at)}</p>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <EmptyPanel
                            title="No generated history"
                            message="Generated summaries will appear here after monitoring activity."
                          />
                        )}
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            </section>
            ) : null}
          </>
      </main>
    </div>
  );
}

function FamilyDashboard({ token, onLogout }) {
  const [data, setData] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const response = await axios.get(`${API_BASE}/mobile/activity-log/`, authConfig(token));
        setData(response.data);
      } catch (err) {
        if (err.response?.status === 401) {
          onLogout();
        } else if (err.response?.status === 404) {
          setErrorMsg('No residents assigned to your account yet.');
        } else if (err.response?.status === 403) {
          setErrorMsg('Access forbidden. You might not have the correct role permissions.');
        } else {
          setErrorMsg('An error occurred while fetching your dashboard.');
        }
      } finally {
        setLoading(false);
      }
    };
    fetchDashboard();
  }, [token, onLogout]);

  if (loading) {
    return <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--midnight-green)' }}><h2>Loading AI Telemetry...</h2></div>;
  }

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
    <div style={shellStyle}>
      <aside style={sidebarStyle}>
        <div style={{ padding: '1.5rem 2rem', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
          <Link to="/">
            <img src="/LOGO_AURACARE.png" alt="AuraCare Logo" style={{ height: '40px' }} />
          </Link>
        </div>
        <nav style={{ flex: 1, padding: '1rem' }}>
          <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', listStyle: 'none', padding: 0 }}>
            <li>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: 'var(--border-radius-sm)', color: 'var(--moonstone)' }}>
                <Activity size={18} /> Overview
              </div>
            </li>
            <li>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '10px 15px', color: 'rgba(255,255,255,0.7)' }}>
                <ShieldAlert size={18} /> Incident Logs
              </div>
            </li>
          </ul>
        </nav>
        <div style={{ padding: '2rem' }}>
          <button onClick={onLogout} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'rgba(255,255,255,0.7)', width: '100%', background: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem' }}>
            <LogOut size={18} /> Sign Out
          </button>
        </div>
      </aside>

      <main style={{ flex: 1, padding: '3rem' }}>
        {errorMsg ? (
          <div style={{ ...panelStyle, padding: '3rem', textAlign: 'center' }}>
            <AlertCircle size={48} color="var(--moonstone)" style={{ marginBottom: '1rem' }} />
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
              <div style={{ ...panelStyle, padding: '10px 20px' }}>
                <span style={{ color: 'var(--text-light)', fontSize: '0.9rem' }}>Status: </span>
                <span style={{ color: 'var(--moonstone)', fontWeight: 'bold' }}>Active & Secure</span>
              </div>
            </header>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '2rem', marginBottom: '3rem' }}>
              <MetricCard
                title="Social Interaction Score"
                value={data?.average_social_score_7d ? data.average_social_score_7d.toFixed(1) : 'N/A'}
                subtitle="Last 7 Days Avg"
                accent="var(--midnight-green)"
              />
              <MetricCard
                title="Recent Incidents"
                value={data?.recent_incidents?.length || 0}
                subtitle="Pending review"
                accent="#EF4444"
              />
              <MetricCard
                title="Recent Summary"
                value={data?.recent_summary ? 'Ready' : 'None'}
                subtitle={data?.recent_summary?.location || 'No location data'}
                accent="var(--moonstone)"
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '2rem' }}>
              <div style={{ ...panelStyle, padding: '2rem' }}>
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

              <div style={{ ...panelStyle, padding: '2rem' }}>
                <h3 style={{ color: 'var(--midnight-green)', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <AlertCircle color="#EF4444" /> Incident Feed
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {data?.recent_incidents && data.recent_incidents.length > 0 ? (
                    data.recent_incidents.map((incident, idx) => (
                      <div key={idx} style={{ padding: '1rem', borderLeft: '4px solid #EF4444', backgroundColor: 'var(--alice-blue)', borderRadius: '0 var(--border-radius-sm) var(--border-radius-sm) 0' }}>
                        <p style={{ margin: '0 0 0.5rem 0', fontWeight: 'bold', color: 'var(--midnight-green)' }}>{incident.type_display} detected</p>
                        <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-light)' }}>Zone: {incident.zone?.name || 'Unknown'}</p>
                        <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-light)' }}>{new Date(incident.timestamp).toLocaleString()}</p>
                      </div>
                    ))
                  ) : (
                    <p style={{ color: 'var(--text-light)', fontStyle: 'italic' }}>No recent incidents.</p>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const token = localStorage.getItem('access_token');

  if (!token) {
    return <Navigate to="/login" />;
  }

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    navigate('/login');
  };

  let role = 'FAMILY';
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(window.atob(base64).split('').map((char) => (`%${(`00${char.charCodeAt(0).toString(16)}`).slice(-2)}`)).join(''));

    const decoded = JSON.parse(jsonPayload);
    if (decoded && decoded.role) {
      role = decoded.role;
    }
  } catch (err) {
    console.error('Invalid token format', err);
  }

  if (role === 'CAREGIVER' || role === 'ADMIN') {
    return <StaffDashboard token={token} onLogout={handleLogout} />;
  }

  return <FamilyDashboard token={token} onLogout={handleLogout} />;
}
