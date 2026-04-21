import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import {
  Activity,
  AlertTriangle,
  CalendarDays,
  ChartColumn,
  Play,
  RefreshCcw,
  Sparkles,
  StopCircle,
  Upload,
  Video,
  Wand2,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const API_HOST = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';
const API_BASE = `http://${API_HOST}:8000/api`;

const cardStyle = {
  backgroundColor: 'white',
  borderRadius: 'var(--border-radius)',
  boxShadow: 'var(--box-shadow)',
  padding: '1.5rem',
};

const metricStyle = {
  backgroundColor: '#F8FAFC',
  borderRadius: '16px',
  padding: '1rem',
  border: '1px solid #E2E8F0',
};

const riskColor = (value) => {
  if (value >= 65) return '#DC2626';
  if (value >= 35) return '#D97706';
  return '#059669';
};

const miniStat = (label, value, accent, hint) => ({ label, value, accent, hint });

function formatDate(value) {
  if (!value) return 'Not available';
  return new Date(value).toLocaleString();
}

function formatNumber(value, fractionDigits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'N/A';
  return Number(value).toFixed(fractionDigits);
}

export default function WanderingDetection({ token, onLogout }) {
  const [loading, setLoading] = useState(true);
  const [launching, setLaunching] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [status, setStatus] = useState(null);
  const [artifacts, setArtifacts] = useState(null);
  const [error, setError] = useState('');
  const [activeView, setActiveView] = useState('live');
  const [cameraRunning, setCameraRunning] = useState(false);
  const [cameraLoading, setCameraLoading] = useState(false);
  const [cameraError, setCameraError] = useState('');
  const [uploadFile, setUploadFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadResult, setUploadResult] = useState(null);
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  const authHeaders = { Authorization: `Bearer ${token}` };

  const loadData = async () => {
    try {
      setError('');
      const [statusResponse, artifactsResponse] = await Promise.all([
        axios.get(`${API_BASE}/models/modelayoub/status/`, { headers: authHeaders }),
        axios.get(`${API_BASE}/models/modelayoub/artifacts/`, { headers: authHeaders }),
      ]);
      setStatus(statusResponse.data || {});
      setArtifacts(artifactsResponse.data || {});
    } catch (requestError) {
      if (requestError.response?.status === 401) {
        onLogout();
        return;
      }
      setError(requestError.response?.data?.error || 'Unable to load wandering detection data right now.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!status?.running) return undefined;
    const timer = window.setInterval(() => {
      void loadData();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [status?.running]);

  const handleLaunch = async (inputMode = 'webcam') => {
    setLaunching(true);
    try {
      const payload = inputMode === 'upload'
        ? { input_mode: 'upload', video_input_path: uploadResult?.video_path || null }
        : { input_mode: 'webcam', webcam_index: 0 };
      const response = await axios.post(`${API_BASE}/models/modelayoub/launch/`, payload, { headers: authHeaders });
      setStatus(response.data || {});
      await loadData();
    } catch (requestError) {
      if (requestError.response?.status === 401) {
        onLogout();
        return;
      }
      setError(requestError.response?.data?.error || 'Unable to launch the wandering detection pipeline.');
    } finally {
      setLaunching(false);
    }
  };

  const handleStop = async () => {
    setStopping(true);
    try {
      const response = await axios.post(`${API_BASE}/models/modelayoub/stop/`, {}, { headers: authHeaders });
      setStatus(response.data || {});
      await loadData();
    } catch (requestError) {
      if (requestError.response?.status === 401) {
        onLogout();
        return;
      }
      setError(requestError.response?.data?.error || 'Unable to stop the wandering detection pipeline.');
    } finally {
      setStopping(false);
    }
  };

  const startCameraPreview = async () => {
    setCameraLoading(true);
    setCameraError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      streamRef.current = stream;
      setCameraRunning(true);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch (previewError) {
      setCameraError(previewError?.message || 'Unable to open the webcam preview.');
    } finally {
      setCameraLoading(false);
    }
  };

  const stopCameraPreview = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraRunning(false);
  };

  const handleUploadLaunch = async () => {
    if (!uploadFile) return;
    setUploading(true);
    setUploadProgress(0);
    setUploadResult(null);

    const form = new FormData();
    form.append('video_file', uploadFile);

    let pct = 0;
    const anim = window.setInterval(() => {
      pct = Math.min(pct + 6, 92);
      setUploadProgress(pct);
    }, 180);

    try {
      const response = await axios.post(`${API_BASE}/models/modelayoub/upload/`, form, {
        headers: { ...authHeaders, 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      });
      window.clearInterval(anim);
      setUploadProgress(100);
      setUploadResult(response.data || null);
      if (response.data?.status) {
        setStatus(response.data.status);
      }
      await loadData();
      setActiveView('overview');
    } catch (requestError) {
      window.clearInterval(anim);
      if (requestError.response?.status === 401) {
        onLogout();
        return;
      }
      setError(requestError.response?.data?.error || 'Unable to upload and launch the wandering analysis.');
    } finally {
      setUploading(false);
    }
  };

  const summary = artifacts?.tracking_summary || {};
  const processingStats = summary.processing_stats || {};
  const trajectoryStats = summary.trajectory_stats || {};
  const riskReport = artifacts?.wandering_risk_report || {};
  const riskTracks = Array.isArray(riskReport.tracks) ? riskReport.tracks : [];
  const trackSeries = riskTracks.map((track) => ({
    id: String(track.track_id ?? 'unknown'),
    score: Number(track.risk_score || 0),
    label: `Track ${track.track_id}`,
  }));
  const trajectoryPreview = Array.isArray(artifacts?.sampled_trajectories) ? artifacts.sampled_trajectories : [];
  const reportFiles = Array.isArray(artifacts?.report_files) ? artifacts.report_files : [];

  const metrics = [
    miniStat('Frames processed', processingStats.frames_processed ?? 0, '#0F766E', 'From tracking summary'),
    miniStat('Unique tracks', processingStats.unique_tracks ?? 0, '#0369A1', 'Detected across the run'),
    miniStat('High-risk tracks', riskReport.metadata?.high_risk_tracks ?? 0, '#DC2626', 'Wandering alerts'),
    miniStat('Low-risk tracks', riskReport.metadata?.low_risk_tracks ?? 0, '#059669', 'Stable movement'),
  ];

  const currentMode = status?.input_mode === 'upload' ? 'Video upload' : 'Webcam live';
  const running = Boolean(status?.running);

  const topTabStyle = (active) => ({
    ...cardStyle,
    padding: '0.8rem 1rem',
    border: 'none',
    cursor: 'pointer',
    background: active ? 'var(--midnight-green)' : 'white',
    color: active ? 'white' : 'var(--midnight-green)',
    fontWeight: 700,
  });

  const sectionTitleStyle = {
    margin: '0 0 0.35rem',
    color: 'var(--midnight-green)',
  };

  if (loading) {
    return (
      <div style={{ padding: '2.5rem', background: 'var(--alice-blue)', minHeight: '100vh' }}>
        <div style={cardStyle}>
          <p style={{ margin: 0, color: 'var(--midnight-green)', fontWeight: 700 }}>Loading wandering detection analytics...</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '2.5rem', background: 'var(--alice-blue)', minHeight: '100vh', overflowY: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap', marginBottom: '2rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.35rem' }}>
            <div style={{ width: '44px', height: '44px', borderRadius: '14px', background: 'linear-gradient(135deg, #F59E0B, #F97316)', display: 'grid', placeItems: 'center', color: 'white', boxShadow: '0 10px 25px rgba(249, 115, 22, 0.24)' }}>
              <Wand2 size={20} />
            </div>
            <div>
              <h1 style={{ margin: 0, color: 'var(--midnight-green)', fontSize: '1.9rem' }}>Wandering Detection</h1>
              <p style={{ margin: '0.25rem 0 0', color: 'var(--text-light)' }}>Launch the model, inspect the latest risk scores, and review exported trajectories.</p>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginTop: '1rem' }}>
            <button
              type="button"
              onClick={() => handleLaunch(activeView === 'upload' ? 'upload' : 'webcam')}
              disabled={launching || running}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.85rem 1.2rem',
                borderRadius: '14px',
                border: 'none',
                cursor: launching || running ? 'not-allowed' : 'pointer',
                background: 'linear-gradient(135deg, #0F766E, #14B8A6)',
                color: 'white',
                fontWeight: 700,
                boxShadow: '0 12px 30px rgba(15, 118, 110, 0.24)',
                opacity: launching || running ? 0.72 : 1,
              }}
            >
              <Play size={16} />
              {running ? 'Pipeline Running' : launching ? 'Launching...' : 'Launch Pipeline'}
            </button>
            <button
              type="button"
              onClick={handleStop}
              disabled={stopping || !running}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.85rem 1.2rem',
                borderRadius: '14px',
                border: 'none',
                cursor: stopping || !running ? 'not-allowed' : 'pointer',
                background: '#DC2626',
                color: 'white',
                fontWeight: 700,
                opacity: stopping || !running ? 0.72 : 1,
              }}
            >
              <StopCircle size={16} />
              {stopping ? 'Stopping...' : 'Stop Pipeline'}
            </button>
            <button
              type="button"
              onClick={loadData}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.85rem 1.2rem',
                borderRadius: '14px',
                border: '1px solid #D7E3EA',
                cursor: 'pointer',
                background: 'white',
                color: 'var(--midnight-green)',
                fontWeight: 700,
              }}
            >
              <RefreshCcw size={16} />
              Refresh
            </button>
          </div>
        </div>

        <div style={{ ...cardStyle, minWidth: '280px', alignSelf: 'flex-start', borderTop: '4px solid #F59E0B' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', marginBottom: '0.75rem' }}>
            <div>
              <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.8rem', fontWeight: 700 }}>Pipeline status</p>
              <h3 style={{ margin: '0.25rem 0 0', color: 'var(--midnight-green)' }}>{running ? 'Running' : 'Idle'}</h3>
            </div>
            <div style={{ width: '42px', height: '42px', borderRadius: '14px', display: 'grid', placeItems: 'center', background: running ? '#DCFCE7' : '#FEF3C7', color: running ? '#047857' : '#B45309' }}>
              <Sparkles size={18} />
            </div>
          </div>
          <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.9rem' }}>{status?.message || 'No active run detected.'}</p>
          <div style={{ marginTop: '0.75rem', padding: '0.85rem 1rem', borderRadius: '14px', background: '#FFF7ED', color: '#9A3412', fontSize: '0.9rem', fontWeight: 700 }}>
            {currentMode}{status?.video_input_path ? ` · ${status.video_input_path}` : ''}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem', marginTop: '1rem' }}>
            <div style={metricStyle}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', fontWeight: 700 }}>PID</div>
              <div style={{ fontSize: '1.05rem', color: 'var(--midnight-green)', fontWeight: 800 }}>{status?.pid || '—'}</div>
            </div>
            <div style={metricStyle}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', fontWeight: 700 }}>Last start</div>
              <div style={{ fontSize: '0.9rem', color: 'var(--midnight-green)', fontWeight: 700 }}>{formatDate(status?.started_at)}</div>
            </div>
          </div>
          <div style={{ marginTop: '1rem', fontSize: '0.85rem', color: 'var(--text-light)' }}>
            {status?.ended_at ? `Ended: ${formatDate(status.ended_at)}` : 'The latest run is still active or has not produced an end timestamp yet.'}
          </div>
        </div>
      </div>

      {error ? (
        <div style={{ ...cardStyle, borderLeft: '4px solid #DC2626', marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', color: '#B91C1C' }}>
            <AlertTriangle size={18} />
            <strong>{error}</strong>
          </div>
        </div>
      ) : null}

      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
        <button type="button" onClick={() => setActiveView('live')} style={topTabStyle(activeView === 'live')}>
          <Video size={16} /> Live View
        </button>
        <button type="button" onClick={() => setActiveView('upload')} style={topTabStyle(activeView === 'upload')}>
          <Upload size={16} /> Upload Video
        </button>
        <button type="button" onClick={() => setActiveView('overview')} style={topTabStyle(activeView === 'overview')}>
          <Activity size={16} /> Overview
        </button>
        <button type="button" onClick={() => setActiveView('reports')} style={topTabStyle(activeView === 'reports')}>
          <ChartColumn size={16} /> Reports
        </button>
        <button type="button" onClick={() => setActiveView('trajectories')} style={topTabStyle(activeView === 'trajectories')}>
          <CalendarDays size={16} /> Trajectories
        </button>
      </div>

      {activeView === 'live' ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.8fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
          <div style={cardStyle}>
            <h3 style={sectionTitleStyle}>Live Webcam Preview</h3>
            <p style={{ margin: '0 0 1rem', color: 'var(--text-light)', fontSize: '0.9rem' }}>Open the camera preview, then launch the wandering pipeline in webcam mode.</p>
            <div style={{ position: 'relative', borderRadius: '18px', overflow: 'hidden', background: '#0F172A', aspectRatio: '16 / 9', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {!cameraRunning ? (
                <div style={{ textAlign: 'center', color: '#94A3B8' }}>
                  <Video size={56} style={{ opacity: 0.25, marginBottom: '0.5rem' }} />
                  <p style={{ margin: 0 }}>Start the webcam preview to see the live view.</p>
                </div>
              ) : null}
              <video ref={videoRef} muted playsInline style={{ display: cameraRunning ? 'block' : 'none', width: '100%', height: '100%', objectFit: 'cover' }} />
              {cameraRunning ? (
                <div style={{ position: 'absolute', top: '12px', right: '12px', background: 'rgba(4, 120, 87, 0.9)', color: 'white', padding: '0.35rem 0.7rem', borderRadius: '999px', fontSize: '0.75rem', fontWeight: 800 }}>
                  LIVE PREVIEW
                </div>
              ) : null}
            </div>
            {cameraError ? <p style={{ color: '#B91C1C', margin: '0.75rem 0 0' }}>{cameraError}</p> : null}
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem', flexWrap: 'wrap' }}>
              {!cameraRunning ? (
                <button type="button" onClick={startCameraPreview} disabled={cameraLoading} style={{ padding: '0.85rem 1rem', borderRadius: '14px', border: 'none', background: 'var(--midnight-green)', color: 'white', fontWeight: 700, cursor: cameraLoading ? 'not-allowed' : 'pointer' }}>
                  {cameraLoading ? 'Starting...' : 'Start Preview'}
                </button>
              ) : (
                <button type="button" onClick={stopCameraPreview} style={{ padding: '0.85rem 1rem', borderRadius: '14px', border: 'none', background: '#DC2626', color: 'white', fontWeight: 700, cursor: 'pointer' }}>
                  <StopCircle size={16} /> Stop Preview
                </button>
              )}
              <button type="button" onClick={() => handleLaunch('webcam')} disabled={launching || running} style={{ padding: '0.85rem 1rem', borderRadius: '14px', border: 'none', background: 'linear-gradient(135deg, #0F766E, #14B8A6)', color: 'white', fontWeight: 700, cursor: launching || running ? 'not-allowed' : 'pointer', opacity: launching || running ? 0.72 : 1 }}>
                <Play size={16} /> {launching ? 'Launching...' : 'Launch Pipeline'}
              </button>
            </div>
          </div>

          <div style={cardStyle}>
            <h3 style={sectionTitleStyle}>Webcam Mode</h3>
            <p style={{ margin: '0 0 1rem', color: 'var(--text-light)', fontSize: '0.9rem' }}>This mode reads from the live camera and writes the latest wandering metrics to the dashboard.</p>
            <div style={{ display: 'grid', gap: '0.85rem' }}>
              <div style={metricStyle}>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-light)', fontWeight: 700 }}>Input</div>
                <div style={{ fontWeight: 800, color: 'var(--midnight-green)', fontSize: '1.1rem' }}>Webcam 0</div>
              </div>
              <div style={metricStyle}>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-light)', fontWeight: 700 }}>Display</div>
                <div style={{ fontWeight: 800, color: 'var(--midnight-green)', fontSize: '1.1rem' }}>Browser live preview</div>
              </div>
              <div style={metricStyle}>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-light)', fontWeight: 700 }}>Output</div>
                <div style={{ fontWeight: 800, color: 'var(--midnight-green)', fontSize: '1.1rem' }}>Risk report + trajectories</div>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {activeView === 'upload' ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
          <div style={cardStyle}>
            <h3 style={sectionTitleStyle}>Upload a Video</h3>
            <p style={{ margin: '0 0 1rem', color: 'var(--text-light)', fontSize: '0.9rem' }}>Upload a file and the backend will run the wandering pipeline on it automatically.</p>
            <label style={{ display: 'block', border: '1px dashed #CBD5E1', borderRadius: '18px', padding: '1.5rem', background: uploadFile ? '#F0FDFC' : 'var(--alice-blue)', cursor: 'pointer' }}>
              <input
                type="file"
                accept="video/*"
                style={{ display: 'none' }}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  setUploadFile(file || null);
                  setUploadResult(null);
                  setUploadProgress(0);
                }}
              />
              {uploadFile ? (
                <div>
                  <div style={{ fontWeight: 800, color: 'var(--midnight-green)', marginBottom: '0.25rem' }}>{uploadFile.name}</div>
                  <div style={{ color: 'var(--text-light)', fontSize: '0.9rem' }}>{(uploadFile.size / 1024 / 1024).toFixed(1)} MB · Ready to launch</div>
                </div>
              ) : (
                <div style={{ color: 'var(--text-light)' }}>
                  <Upload size={22} style={{ marginRight: '0.5rem', verticalAlign: 'middle' }} />
                  Choose a video file to analyze
                </div>
              )}
            </label>
            {uploadProgress > 0 ? (
              <div style={{ marginTop: '1rem' }}>
                <div style={{ height: '10px', borderRadius: '999px', background: '#E2E8F0', overflow: 'hidden' }}>
                  <div style={{ width: `${uploadProgress}%`, height: '100%', background: 'linear-gradient(90deg, #0F766E, #14B8A6)' }} />
                </div>
                <p style={{ margin: '0.4rem 0 0', color: 'var(--text-light)', fontSize: '0.85rem' }}>{uploadProgress}% uploaded / processing</p>
              </div>
            ) : null}
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem', flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={handleUploadLaunch}
                disabled={!uploadFile || uploading || running}
                style={{ padding: '0.85rem 1rem', borderRadius: '14px', border: 'none', background: 'linear-gradient(135deg, #0F766E, #14B8A6)', color: 'white', fontWeight: 700, cursor: !uploadFile || uploading || running ? 'not-allowed' : 'pointer', opacity: !uploadFile || uploading || running ? 0.72 : 1 }}
              >
                {uploading ? 'Uploading...' : 'Upload & Launch'}
              </button>
              <button type="button" onClick={() => { setUploadFile(null); setUploadResult(null); setUploadProgress(0); }} style={{ padding: '0.85rem 1rem', borderRadius: '14px', border: '1px solid #D7E3EA', background: 'white', color: 'var(--midnight-green)', fontWeight: 700, cursor: 'pointer' }}>
                Clear
              </button>
            </div>
            {uploadResult ? (
              <div style={{ marginTop: '1rem', padding: '1rem', borderRadius: '14px', background: '#ECFDF5', color: '#065F46', border: '1px solid #6EE7B7' }}>
                <div style={{ fontWeight: 800, marginBottom: '0.25rem' }}>Upload launched successfully</div>
                <div style={{ fontSize: '0.9rem' }}>{uploadResult.filename}</div>
                <div style={{ fontSize: '0.85rem' }}>{uploadResult.video_path}</div>
              </div>
            ) : null}
          </div>

          <div style={cardStyle}>
            <h3 style={sectionTitleStyle}>Video Upload Mode</h3>
            <p style={{ margin: '0 0 1rem', color: 'var(--text-light)', fontSize: '0.9rem' }}>The backend saves the file, switches the model to file input mode, and runs the full pipeline.</p>
            <div style={{ display: 'grid', gap: '0.85rem' }}>
              <div style={metricStyle}>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-light)', fontWeight: 700 }}>Backend input</div>
                <div style={{ fontWeight: 800, color: 'var(--midnight-green)', fontSize: '1.1rem' }}>WANDER_USE_WEBCAM=0</div>
              </div>
              <div style={metricStyle}>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-light)', fontWeight: 700 }}>Model file</div>
                <div style={{ fontWeight: 800, color: 'var(--midnight-green)', fontSize: '1.05rem', wordBreak: 'break-word' }}>{uploadResult?.video_path || 'Awaiting upload'}</div>
              </div>
              <div style={metricStyle}>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-light)', fontWeight: 700 }}>Output</div>
                <div style={{ fontWeight: 800, color: 'var(--midnight-green)', fontSize: '1.1rem' }}>Same risk and trajectory reports</div>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {activeView === 'overview' ? (
        <>
          {running && (
            <div style={{ marginBottom: '1.5rem', borderRadius: '18px', overflow: 'hidden', background: '#000', aspectRatio: '16 / 9', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <video
                src="http://localhost:8000/api/models/modelayoub/stream/"
                controls
                autoPlay
                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
              />
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 0.9fr', gap: '1.5rem' }}>
            <div style={cardStyle}>
              <h3 style={sectionTitleStyle}>Risk Score by Track</h3>
              <p style={{ margin: '0 0 1rem', color: 'var(--text-light)', fontSize: '0.9rem' }}>Higher scores indicate a stronger wandering signal.</p>
              {trackSeries.length > 0 ? (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={trackSeries} barSize={42}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E9F1F6" />
                  <XAxis dataKey="label" axisLine={false} tickLine={false} />
                  <YAxis domain={[0, 100]} axisLine={false} tickLine={false} />
                  <Tooltip formatter={(value) => [`${Number(value).toFixed(1)}%`, 'Risk score']} />
                  <Bar dataKey="score" radius={[12, 12, 0, 0]}>
                    {trackSeries.map((entry) => (
                      <Cell key={entry.id} fill={riskColor(entry.score)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ padding: '2rem', color: 'var(--text-light)' }}>No risk tracks available yet.</div>
            )}
          </div>

          <div style={cardStyle}>
            <h3 style={sectionTitleStyle}>Run Summary</h3>
            <p style={{ margin: '0 0 1rem', color: 'var(--text-light)', fontSize: '0.9rem' }}>Core statistics extracted from tracking_summary.json.</p>
            <div style={{ display: 'grid', gap: '0.9rem' }}>
              <div style={metricStyle}>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-light)', fontWeight: 700 }}>Frames with detections</div>
                <div style={{ fontWeight: 800, color: 'var(--midnight-green)', fontSize: '1.35rem' }}>{processingStats.frames_with_detections ?? 'N/A'}</div>
              </div>
              <div style={metricStyle}>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-light)', fontWeight: 700 }}>Average track length</div>
                <div style={{ fontWeight: 800, color: 'var(--midnight-green)', fontSize: '1.35rem' }}>{formatNumber(processingStats.avg_track_length, 1)}</div>
              </div>
              <div style={metricStyle}>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-light)', fontWeight: 700 }}>Detected tracks</div>
                <div style={{ fontWeight: 800, color: 'var(--midnight-green)', fontSize: '1.35rem' }}>{trajectoryStats.total_unique_tracks ?? summary.processing_stats?.unique_tracks ?? 0}</div>
              </div>
            </div>
          </div>
        </div>
        </>
      ) : null}

      {activeView === 'reports' ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
          <div style={cardStyle}>
            <h3 style={sectionTitleStyle}>Wandering Risk Report</h3>
            <p style={{ margin: '0 0 1rem', color: 'var(--text-light)', fontSize: '0.9rem' }}>Track-level risk analysis from wandering_risk_report.json.</p>
            <div style={{ display: 'grid', gap: '0.85rem' }}>
              {riskTracks.length > 0 ? riskTracks.map((track) => (
                <div key={track.track_id} style={{ border: '1px solid #E2E8F0', borderRadius: '16px', padding: '1rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontWeight: 800, color: 'var(--midnight-green)' }}>Track {track.track_id}</div>
                      <div style={{ color: 'var(--text-light)', fontSize: '0.82rem' }}>{track.num_points} points · {formatNumber(track.duration_s, 1)}s</div>
                    </div>
                    <div style={{ fontWeight: 900, color: riskColor(track.risk_score), fontSize: '1.4rem' }}>{formatNumber(track.risk_score, 1)}%</div>
                  </div>
                  <div style={{ marginTop: '0.8rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap', color: 'var(--text-light)', fontSize: '0.82rem' }}>
                    <span>Level: <strong style={{ color: 'var(--midnight-green)' }}>{String(track.risk_level || 'unknown').toUpperCase()}</strong></span>
                    <span>Turn rate: <strong style={{ color: 'var(--midnight-green)' }}>{formatNumber(track.turn_rate_per_min, 1)}</strong></span>
                    <span>Tortuosity: <strong style={{ color: 'var(--midnight-green)' }}>{formatNumber(track.tortuosity, 1)}</strong></span>
                  </div>
                </div>
              )) : <div style={{ color: 'var(--text-light)' }}>No per-track risk metrics are available yet.</div>}
            </div>
          </div>

          <div style={cardStyle}>
            <h3 style={sectionTitleStyle}>Generated Files</h3>
            <p style={{ margin: '0 0 1rem', color: 'var(--text-light)', fontSize: '0.9rem' }}>Artifacts written to the model tracking_results folder.</p>
            <div style={{ display: 'grid', gap: '0.75rem' }}>
              {reportFiles.length > 0 ? reportFiles.map((file) => (
                <div key={file.name} style={{ border: '1px solid #E2E8F0', borderRadius: '14px', padding: '0.9rem 1rem', display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
                  <div>
                    <div style={{ fontWeight: 800, color: 'var(--midnight-green)' }}>{file.name}</div>
                    <div style={{ color: 'var(--text-light)', fontSize: '0.82rem' }}>{file.size_bytes} bytes</div>
                  </div>
                  <div style={{ color: 'var(--text-light)', fontSize: '0.8rem', maxWidth: '55%', textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis' }}>{file.path}</div>
                </div>
              )) : <div style={{ color: 'var(--text-light)' }}>No artifact files were found yet.</div>}
            </div>
          </div>
        </div>
      ) : null}

      {activeView === 'trajectories' ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: '1.5rem' }}>
          <div style={cardStyle}>
            <h3 style={sectionTitleStyle}>Trajectory Preview</h3>
            <p style={{ margin: '0 0 1rem', color: 'var(--text-light)', fontSize: '0.9rem' }}>The first sampled points from trajectories.json are shown below.</p>
            <div style={{ display: 'grid', gap: '1rem' }}>
              {trajectoryPreview.length > 0 ? trajectoryPreview.map((track) => {
                const points = Array.isArray(track.points) ? track.points : [];
                const trail = points.slice(0, 12).map((point) => point.y ?? 0);
                const previewSeries = trail.map((value, index) => ({ idx: index, value }));
                return (
                  <div key={track.track_id} style={{ border: '1px solid #E2E8F0', borderRadius: '16px', padding: '1rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', marginBottom: '0.75rem' }}>
                      <div>
                        <div style={{ fontWeight: 800, color: 'var(--midnight-green)' }}>Track {track.track_id}</div>
                        <div style={{ color: 'var(--text-light)', fontSize: '0.82rem' }}>{points.length} sampled points</div>
                      </div>
                      <div style={{ color: 'var(--text-light)', fontSize: '0.82rem' }}>Preview from trajectories.json</div>
                    </div>
                    <ResponsiveContainer width="100%" height={140}>
                      <LineChart data={previewSeries}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E9F1F6" />
                        <XAxis dataKey="idx" axisLine={false} tickLine={false} hide />
                        <YAxis axisLine={false} tickLine={false} hide />
                        <Tooltip />
                        <Line type="monotone" dataKey="value" stroke="#0F766E" strokeWidth={2.5} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                );
              }) : <div style={{ color: 'var(--text-light)' }}>No trajectory samples are available yet.</div>}
            </div>
          </div>

          <div style={cardStyle}>
            <h3 style={sectionTitleStyle}>Video Metadata</h3>
            <p style={{ margin: '0 0 1rem', color: 'var(--text-light)', fontSize: '0.9rem' }}>Extracted directly from the trajectory export.</p>
            <div style={{ display: 'grid', gap: '0.85rem' }}>
              {[
                { label: 'Video path', value: artifacts?.trajectory_metadata?.video_path || 'N/A' },
                { label: 'FPS', value: formatNumber(artifacts?.trajectory_metadata?.fps, 1) },
                { label: 'Resolution', value: `${artifacts?.trajectory_metadata?.width || 'N/A'} × ${artifacts?.trajectory_metadata?.height || 'N/A'}` },
                { label: 'Total frames', value: artifacts?.trajectory_metadata?.total_frames ?? 'N/A' },
                { label: 'Tracks', value: artifacts?.trajectory_metadata?.total_tracks ?? 'N/A' },
              ].map((item) => (
                <div key={item.label} style={metricStyle}>
                  <div style={{ color: 'var(--text-light)', fontSize: '0.75rem', fontWeight: 700 }}>{item.label}</div>
                  <div style={{ color: 'var(--midnight-green)', fontSize: '1rem', fontWeight: 800, marginTop: '0.25rem', wordBreak: 'break-word' }}>{item.value}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
