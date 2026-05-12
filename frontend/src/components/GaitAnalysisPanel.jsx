import { useEffect, useState } from 'react';
import axios from 'axios';
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  TriangleAlert,
  Upload,
  Video,
} from 'lucide-react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const API_HOST = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';
const API_BASE = `http://${API_HOST}:8000/api`;
const MEDIA_BASE = `http://${API_HOST}:8000`;

const sectionCardStyle = {
  backgroundColor: 'white',
  padding: '1.5rem',
  borderRadius: 'var(--border-radius)',
  boxShadow: 'var(--box-shadow)',
};

const chipButtonStyle = (active) => ({
  padding: '8px 14px',
  borderRadius: '999px',
  border: 'none',
  cursor: 'pointer',
  fontSize: '0.82rem',
  fontWeight: 700,
  backgroundColor: active ? 'var(--midnight-green)' : 'white',
  color: active ? 'white' : 'var(--text-light)',
  boxShadow: active ? 'none' : 'var(--box-shadow)',
});

function GaitBadge({ label, confidence }) {
  const isNormal = label === 'normal';
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.35rem',
        padding: '6px 10px',
        borderRadius: '999px',
        fontSize: '0.78rem',
        fontWeight: 800,
        backgroundColor: isNormal ? '#DCFCE7' : '#FEE2E2',
        color: isNormal ? '#166534' : '#B91C1C',
      }}
    >
      {isNormal ? <CheckCircle2 size={14} /> : <TriangleAlert size={14} />}
      {label ? label.toUpperCase() : 'UNKNOWN'} {Number(confidence || 0).toFixed(0)}%
    </span>
  );
}

function GaitResidentCard({ resident }) {
  const [expanded, setExpanded] = useState(false);
  const observations = resident.observations || [];
  const latestObservation = observations[0];
  const alertCount = observations.filter((observation) => observation.alert_triggered).length;
  const abnormalCount = observations.filter((observation) => observation.label === 'abnormal').length;

  const chartData = observations.slice(0, 7).reverse().map((observation) => ({
    label: new Date(observation.recorded_at).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }),
    confidence: Number(observation.confidence || 0),
  }));

  return (
    <article
      style={{
        ...sectionCardStyle,
        padding: 0,
        overflow: 'hidden',
        border: `1px solid ${alertCount ? '#FECACA' : '#DCE9EF'}`,
      }}
    >
      <div
        style={{
          padding: '1.35rem 1.5rem',
          background: alertCount
            ? 'linear-gradient(135deg, #FFF1F2 0%, #FFFFFF 75%)'
            : 'linear-gradient(135deg, #F7FCFF 0%, #FFFFFF 75%)',
          borderLeft: `5px solid ${alertCount ? '#DC2626' : '#0EA5E9'}`,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: '1rem',
          flexWrap: 'wrap',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <h3 style={{ margin: 0, color: 'var(--midnight-green)' }}>{resident.resident_name}</h3>
            {latestObservation ? (
              <GaitBadge label={latestObservation.label} confidence={latestObservation.confidence} />
            ) : (
              <span style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-light)' }}>No analysis yet</span>
            )}
            {alertCount > 0 && (
              <span
                style={{
                  fontSize: '0.72rem',
                  fontWeight: 800,
                  color: '#991B1B',
                  backgroundColor: '#FEE2E2',
                  borderRadius: '999px',
                  padding: '5px 10px',
                }}
              >
                {alertCount} alert{alertCount > 1 ? 's' : ''}
              </span>
            )}
          </div>
          <p style={{ margin: '0.35rem 0 0', color: 'var(--text-light)', fontSize: '0.88rem' }}>
            Room {resident.room_number} • Age {resident.age} • {resident.risk_level} risk
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{ textAlign: 'right' }}>
            <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.75rem', fontWeight: 700 }}>Abnormal Sessions</p>
            <p style={{ margin: '0.15rem 0 0', color: '#B45309', fontSize: '1.55rem', fontWeight: 800 }}>{abnormalCount}</p>
          </div>
          <button
            type="button"
            onClick={() => setExpanded((current) => !current)}
            style={{
              border: '1px solid #D7E3EA',
              backgroundColor: 'white',
              color: 'var(--midnight-green)',
              borderRadius: '999px',
              padding: '10px 14px',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
            }}
          >
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            {expanded ? 'Hide Details' : 'Open Details'}
          </button>
        </div>
      </div>

      {expanded && (
        <div style={{ padding: '1.5rem' }}>
          {observations.length === 0 ? (
            <div
              style={{
                borderRadius: '18px',
                border: '1px dashed #D7E3EA',
                padding: '2rem',
                textAlign: 'center',
                color: 'var(--text-light)',
              }}
            >
              No gait observations have been recorded for this resident yet.
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.2fr) minmax(0, 1fr)', gap: '1.25rem' }}>
              <div style={{ borderRadius: '18px', backgroundColor: '#F7FBFD', padding: '1rem 1.1rem', border: '1px solid #DCE9EF' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <h4 style={{ margin: 0, color: 'var(--midnight-green)' }}>Confidence Trend</h4>
                  <span style={{ color: 'var(--text-light)', fontSize: '0.76rem', fontWeight: 700 }}>Last 7 sessions</span>
                </div>
                <div style={{ height: '190px' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fontSize: 11 }} />
                      <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fontSize: 11 }} />
                      <Tooltip formatter={(value) => `${Number(value).toFixed(0)}%`} />
                      <Line type="monotone" dataKey="confidence" stroke="#0891B2" strokeWidth={3} dot={{ r: 3 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div style={{ borderRadius: '18px', backgroundColor: '#FCFDFE', padding: '1rem 1.1rem', border: '1px solid #DCE9EF' }}>
                <h4 style={{ margin: '0 0 0.9rem 0', color: 'var(--midnight-green)' }}>Recent Sessions</h4>
                <div style={{ display: 'grid', gap: '0.75rem', maxHeight: '240px', overflowY: 'auto', paddingRight: '0.2rem' }}>
                  {observations.map((observation) => (
                    <div
                      key={observation.id}
                      style={{
                        padding: '0.85rem',
                        borderRadius: '14px',
                        backgroundColor: observation.label === 'abnormal' ? '#FFF5F5' : '#F0FDF4',
                        border: `1px solid ${observation.label === 'abnormal' ? '#FECACA' : '#BBF7D0'}`,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                        <GaitBadge label={observation.label} confidence={observation.confidence} />
                        <span style={{ color: 'var(--text-light)', fontSize: '0.76rem' }}>
                          {new Date(observation.recorded_at).toLocaleString('fr-FR', {
                            day: '2-digit',
                            month: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </span>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '0.45rem', marginTop: '0.8rem' }}>
                        {Object.entries(observation.features || {}).slice(0, 6).map(([key, value]) => (
                          <div key={key} style={{ fontSize: '0.78rem', color: 'var(--text-light)' }}>
                            <span>{key.replaceAll('_', ' ')}</span>
                            <strong style={{ color: 'var(--midnight-green)', marginLeft: '0.35rem' }}>
                              {Number(value || 0).toFixed(2)}
                            </strong>
                          </div>
                        ))}
                      </div>

                      {observation.snapshot && (
                        <button
                          type="button"
                          onClick={() => window.open(`${MEDIA_BASE}${observation.snapshot}`, '_blank', 'noopener,noreferrer')}
                          style={{
                            marginTop: '0.85rem',
                            border: 'none',
                            padding: 0,
                            background: 'none',
                            cursor: 'pointer',
                          }}
                        >
                          <img
                            src={`${MEDIA_BASE}${observation.snapshot}`}
                            alt="Gait snapshot"
                            style={{ width: '100%', maxWidth: '180px', borderRadius: '12px', border: '1px solid #D7E3EA', objectFit: 'cover' }}
                          />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </article>
  );
}

export default function GaitAnalysisPanel({ token, onLogout }) {
  const [residents, setResidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [filter, setFilter] = useState('all');
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploadStatus, setUploadStatus] = useState('idle');
  const [uploadMessage, setUploadMessage] = useState('');

  const fetchGaitData = async ({ silent = false } = {}) => {
    if (silent) setRefreshing(true);
    else setLoading(true);

    try {
      const response = await axios.get(`${API_BASE}/gait/all/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setResidents(response.data || []);
      setErrorMsg('');
    } catch (error) {
      if (error.response?.status === 401) onLogout();
      else if (error.response?.status === 403) setErrorMsg('Only caregiver and admin accounts can access the gait module.');
      else setErrorMsg('Unable to load gait analysis history right now.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchGaitData();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const totalObservations = residents.reduce((sum, resident) => sum + (resident.observations?.length || 0), 0);
  const alertResidents = residents.filter((resident) => resident.observations?.some((observation) => observation.alert_triggered));
  const abnormalResidents = residents.filter((resident) => resident.observations?.[0]?.label === 'abnormal');
  const normalResidents = residents.filter((resident) => resident.observations?.[0]?.label === 'normal');

  const filteredResidents = residents.filter((resident) => {
    if (filter === 'alert') return resident.observations?.some((observation) => observation.alert_triggered);
    if (filter === 'abnormal') return resident.observations?.[0]?.label === 'abnormal';
    if (filter === 'normal') return resident.observations?.[0]?.label === 'normal';
    if (filter === 'empty') return (resident.observations?.length || 0) === 0;
    return true;
  });

  const handleFile = (candidate) => {
    if (candidate && candidate.type.startsWith('video/')) {
      setFile(candidate);
      setUploadStatus('idle');
      setUploadMessage('');
      return;
    }
    setUploadStatus('error');
    setUploadMessage('Please select a valid video file so the gait model can analyze it.');
  };

  const handleSubmit = async () => {
    if (!file) return;

    const formData = new FormData();
    formData.append('video', file);

    setUploadStatus('uploading');
    setUploadMessage('Uploading recording and starting the gait model...');

    try {
      const response = await axios.post(`${API_BASE}/gait/analyze/`, formData, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data',
        },
      });
      setUploadStatus('success');
      setUploadMessage(response.data?.message || 'Analysis started successfully.');
      window.setTimeout(() => {
        fetchGaitData({ silent: true });
      }, 2000);
    } catch (error) {
      if (error.response?.status === 401) onLogout();
      setUploadStatus('error');
      setUploadMessage(error.response?.data?.error || 'Unable to start gait analysis right now.');
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--midnight-green)' }}>
        <h2>Loading gait module...</h2>
      </div>
    );
  }

  return (
    <div style={{ display: 'grid', gap: '1.5rem' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
        <div style={{ ...sectionCardStyle, borderTop: '4px solid #0EA5E9' }}>
          <p style={{ margin: 0, color: 'var(--text-light)', fontWeight: 700 }}>Residents Monitored</p>
          <h2 style={{ margin: '0.45rem 0 0', color: 'var(--midnight-green)', fontSize: '2rem' }}>{residents.length}</h2>
          <p style={{ margin: '0.35rem 0 0', color: 'var(--text-light)', fontSize: '0.9rem' }}>Residents visible in gait history</p>
        </div>
        <div style={{ ...sectionCardStyle, borderTop: '4px solid #DC2626' }}>
          <p style={{ margin: 0, color: 'var(--text-light)', fontWeight: 700 }}>Active Gait Alerts</p>
          <h2 style={{ margin: '0.45rem 0 0', color: '#991B1B', fontSize: '2rem' }}>{alertResidents.length}</h2>
          <p style={{ margin: '0.35rem 0 0', color: 'var(--text-light)', fontSize: '0.9rem' }}>Residents with repeated abnormal sessions</p>
        </div>
        <div style={{ ...sectionCardStyle, borderTop: '4px solid #F59E0B' }}>
          <p style={{ margin: 0, color: 'var(--text-light)', fontWeight: 700 }}>Latest Abnormal</p>
          <h2 style={{ margin: '0.45rem 0 0', color: '#B45309', fontSize: '2rem' }}>{abnormalResidents.length}</h2>
          <p style={{ margin: '0.35rem 0 0', color: 'var(--text-light)', fontSize: '0.9rem' }}>Residents whose last session is abnormal</p>
        </div>
        <div style={{ ...sectionCardStyle, borderTop: '4px solid #059669' }}>
          <p style={{ margin: 0, color: 'var(--text-light)', fontWeight: 700 }}>Total Sessions</p>
          <h2 style={{ margin: '0.45rem 0 0', color: '#065F46', fontSize: '2rem' }}>{totalObservations}</h2>
          <p style={{ margin: '0.35rem 0 0', color: 'var(--text-light)', fontSize: '0.9rem' }}>Normal: {normalResidents.length} residents in latest state</p>
        </div>
      </div>

      <section
        style={{
          ...sectionCardStyle,
          background: 'linear-gradient(135deg, #082F49 0%, #0F766E 50%, #FFFFFF 160%)',
          color: 'white',
          padding: '1.75rem',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div>
            <p style={{ margin: 0, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.12em', opacity: 0.75 }}>
              Gait Module
            </p>
            <h2 style={{ margin: '0.35rem 0 0', fontSize: '2rem' }}>Gait Intelligence Studio</h2>
            <p style={{ margin: '0.7rem 0 0', maxWidth: '42rem', color: 'rgba(255,255,255,0.82)' }}>
              Upload a corridor recording, let the gait model process it in the background, then review resident-by-resident confidence trends, snapshots, and repeated abnormal detections.
            </p>
          </div>
          <button
            type="button"
            onClick={() => fetchGaitData({ silent: true })}
            disabled={refreshing}
            style={{
              border: '1px solid rgba(255,255,255,0.25)',
              backgroundColor: 'rgba(255,255,255,0.08)',
              color: 'white',
              borderRadius: '999px',
              padding: '11px 16px',
              fontWeight: 700,
              cursor: refreshing ? 'not-allowed' : 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              opacity: refreshing ? 0.7 : 1,
            }}
          >
            <RefreshCw size={16} style={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
            {refreshing ? 'Refreshing...' : 'Refresh Results'}
          </button>
        </div>
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 420px) minmax(0, 1fr)', gap: '1.5rem', alignItems: 'start' }}>
        <section style={sectionCardStyle}>
          <h3 style={{ margin: '0 0 0.35rem 0', color: 'var(--midnight-green)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Upload size={18} color="#0EA5E9" /> Upload Recording
          </h3>
          <p style={{ margin: 0, color: 'var(--text-light)', fontSize: '0.92rem' }}>
            Start the same analysis workflow directly from the main dashboard.
          </p>

          <div
            onDragOver={(event) => {
              event.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragOver(false);
              handleFile(event.dataTransfer.files?.[0]);
            }}
            onClick={() => document.getElementById('gait-upload-input')?.click()}
            style={{
              marginTop: '1.25rem',
              border: `2px dashed ${dragOver ? '#0EA5E9' : '#CBD5E1'}`,
              borderRadius: '18px',
              padding: '2.2rem 1.2rem',
              textAlign: 'center',
              backgroundColor: dragOver ? '#F0FDFA' : '#F8FAFC',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
          >
            <input
              id="gait-upload-input"
              type="file"
              accept="video/*"
              style={{ display: 'none' }}
              onChange={(event) => handleFile(event.target.files?.[0])}
            />
            <Video size={38} color={dragOver ? '#0891B2' : '#94A3B8'} />
            {file ? (
              <div style={{ marginTop: '0.85rem' }}>
                <p style={{ margin: 0, fontWeight: 800, color: 'var(--midnight-green)' }}>{file.name}</p>
                <p style={{ margin: '0.35rem 0 0', color: 'var(--text-light)', fontSize: '0.82rem' }}>
                  {(file.size / 1024 / 1024).toFixed(1)} MB ready for gait analysis
                </p>
              </div>
            ) : (
              <div style={{ marginTop: '0.85rem' }}>
                <p style={{ margin: 0, fontWeight: 800, color: 'var(--midnight-green)' }}>Drop a corridor video here or click to browse</p>
                <p style={{ margin: '0.35rem 0 0', color: 'var(--text-light)', fontSize: '0.82rem' }}>MP4, MOV, AVI and other video formats are accepted.</p>
              </div>
            )}
          </div>

          {uploadMessage && (
            <div
              style={{
                marginTop: '1rem',
                padding: '0.95rem 1rem',
                borderRadius: '14px',
                display: 'flex',
                alignItems: 'center',
                gap: '0.6rem',
                backgroundColor: uploadStatus === 'success' ? '#DCFCE7' : uploadStatus === 'error' ? '#FEE2E2' : '#E0F2FE',
                color: uploadStatus === 'success' ? '#166534' : uploadStatus === 'error' ? '#B91C1C' : '#0C4A6E',
              }}
            >
              {uploadStatus === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
              <span style={{ fontWeight: 600 }}>{uploadMessage}</span>
            </div>
          )}

          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginTop: '1rem' }}>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!file || uploadStatus === 'uploading'}
              style={{
                border: 'none',
                borderRadius: '12px',
                padding: '12px 18px',
                backgroundColor: !file || uploadStatus === 'uploading' ? '#CBD5E1' : 'var(--midnight-green)',
                color: 'white',
                fontWeight: 800,
                cursor: !file || uploadStatus === 'uploading' ? 'not-allowed' : 'pointer',
              }}
            >
              {uploadStatus === 'uploading' ? 'Starting Analysis...' : 'Start Gait Analysis'}
            </button>
            {file && uploadStatus !== 'uploading' && (
              <button
                type="button"
                onClick={() => {
                  setFile(null);
                  setUploadStatus('idle');
                  setUploadMessage('');
                }}
                style={{
                  border: '1px solid #D7E3EA',
                  borderRadius: '12px',
                  padding: '12px 18px',
                  backgroundColor: 'white',
                  color: 'var(--text-light)',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                Clear Selection
              </button>
            )}
          </div>
        </section>

        <section style={sectionCardStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            <div>
              <h3 style={{ margin: 0, color: 'var(--midnight-green)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Activity size={18} color="#0EA5E9" /> Gait History
              </h3>
              <p style={{ margin: '0.35rem 0 0', color: 'var(--text-light)', fontSize: '0.92rem' }}>
                Review the latest gait state, repeated alerts, and per-session features.
              </p>
            </div>
            <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
              {['all', 'alert', 'abnormal', 'normal', 'empty'].map((value) => (
                <button key={value} type="button" onClick={() => setFilter(value)} style={chipButtonStyle(filter === value)}>
                  {value.charAt(0).toUpperCase() + value.slice(1)}
                </button>
              ))}
            </div>
          </div>
        </section>
      </div>

      {errorMsg && (
        <div
          style={{
            ...sectionCardStyle,
            backgroundColor: '#FEF2F2',
            color: '#B91C1C',
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
          }}
        >
          <AlertCircle size={20} />
          <strong>{errorMsg}</strong>
        </div>
      )}

      {filteredResidents.length === 0 ? (
        <div
          style={{
            ...sectionCardStyle,
            padding: '3rem',
            textAlign: 'center',
            color: 'var(--text-light)',
          }}
        >
          <Activity size={44} style={{ opacity: 0.35, marginBottom: '0.8rem' }} />
          <p style={{ margin: 0, fontWeight: 700 }}>No gait records match this filter yet.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '1rem' }}>
          {filteredResidents.map((resident) => (
            <GaitResidentCard key={resident.resident_id} resident={resident} />
          ))}
        </div>
      )}
    </div>
  );
}
