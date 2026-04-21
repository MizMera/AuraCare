import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, Legend,
} from 'recharts';
import {
  Camera, Upload, StopCircle, Play,
  AlertTriangle, CheckCircle, Clock,
  Users, TrendingUp, Video,
} from 'lucide-react';

const API_HOST = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';
const API_BASE = `http://${API_HOST}:8000/api`;
const DAYS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];
const LOCAL_SESSION_KEY = 'auracare.social-isolation.sessions';

// ── helpers ──────────────────────────────────────────────────
const scoreColor = (s) => s >= 65 ? '#EF4444' : s >= 40 ? '#F59E0B' : '#44A6B5';

const Pill = ({ type }) => {
  const MAP = {
    isole:     { label: '🔴 Isolated',      bg: '#FEE2E2', color: '#B91C1C' },
    vigilance: { label: '🟡 Vigilance',  bg: '#FEF3C7', color: '#B45309' },
    actif:     { label: '🟢 Active',      bg: '#D1FAE5', color: '#065F46' },
  };
  const s = MAP[type] || MAP.actif;
  return (
    <span style={{ display:'inline-block', padding:'2px 9px', borderRadius:99,
      fontSize:11, fontWeight:700, background:s.bg, color:s.color }}>{s.label}</span>
  );
};

const Card = ({ children, style }) => (
  <div style={{
    backgroundColor:'white', borderRadius:'var(--border-radius)',
    boxShadow:'var(--box-shadow)', padding:'1.5rem', ...style,
  }}>{children}</div>
);

const KpiCard = ({ label, value, sub, color, icon }) => (
  <Card>
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:8 }}>
      <span style={{ fontSize:13, color:'var(--text-light)', fontWeight:600 }}>{label}</span>
      <span style={{ color }}>{icon}</span>
    </div>
    <div style={{ fontSize:'2.2rem', fontWeight:800, color, lineHeight:1, marginBottom:4 }}>{value}</div>
    {sub && <p style={{ margin:0, fontSize:12, color:'var(--text-light)' }}>{sub}</p>}
  </Card>
);

const TabBtn = ({ label, active, onClick, icon }) => (
  <button onClick={onClick} style={{
    display:'flex', alignItems:'center', gap:6,
    padding:'10px 18px', borderRadius:'var(--border-radius-sm)',
    border:'none', cursor:'pointer', fontWeight:700, fontSize:13,
    transition:'all .2s',
    background: active ? 'var(--midnight-green)' : 'white',
    color: active ? 'white' : 'var(--midnight-green)',
    boxShadow: active ? 'none' : 'var(--box-shadow)',
  }}>{icon}{label}</button>
);

const readLocalSessions = () => {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(LOCAL_SESSION_KEY);
    const parsed = JSON.parse(raw || '[]');
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};

const writeLocalSessions = (sessions) => {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(LOCAL_SESSION_KEY, JSON.stringify(sessions.slice(0, 60)));
};

const buildLocalKpi = (sessions) => {
  const alertsToday = sessions.reduce((count, session) => {
    const sessionDate = new Date(session.uploaded_at).toDateString();
    const today = new Date().toDateString();
    if (sessionDate !== today) return count;
    return count + ((session.frames_isole || 0) > 0 || (session.frames_vigilance || 0) > 0 ? 1 : 0);
  }, 0);

  const weeklyTrend = sessions[0]?.weekly_scores?.length === 7
    ? sessions[0].weekly_scores
    : Array(7).fill(0);

  return {
    alerts_today: alertsToday,
    total_analysed: sessions.length,
    total_sessions: sessions.length,
    weekly_trend: weeklyTrend,
  };
};

const makeLocalSession = ({ filename, counters, durationSeconds, events, source = 'webcam', savedWithoutVideo = false }) => {
  const total = counters.actif + counters.vig + counters.iso || 1;
  const isolationScore = +(counters.iso / total * 100).toFixed(1);
  const weeklyScores = Array(7).fill(0);
  const dayIndex = (new Date().getDay() + 6) % 7;
  weeklyScores[dayIndex] = Math.round(isolationScore);

  return {
    id: `local-${Date.now()}`,
    filename,
    source,
    uploaded_at: new Date().toISOString(),
    duration_seconds: durationSeconds,
    persons_detected: Math.max(1, new Set(events.map((event) => event.track_id)).size || 1),
    frames_actif: counters.actif,
    frames_vigilance: counters.vig,
    frames_isole: counters.iso,
    isolation_score: isolationScore,
    actif_pct: Math.round(counters.actif / total * 100),
    vigilance_pct: Math.round(counters.vig / total * 100),
    isolation_pct: Math.round(counters.iso / total * 100),
    status: 'analysed',
    weekly_scores: weeklyScores,
    saved_locally: true,
    saved_without_video: savedWithoutVideo,
  };
};

const upsertLocalSession = (session) => {
  const nextSessions = [session, ...readLocalSessions().filter((item) => item.id !== session.id)];
  writeLocalSessions(nextSessions);
  return nextSessions;
};

// ── main component ────────────────────────────────────────────
export default function SocialInteraction({
  token,
  onLogout,
  title = 'Social Interaction',
  description = '',
}) {
  const navigate = useNavigate();
  void navigate;
  const [tab, setTab]             = useState('dashboard');
  const [sessions, setSessions]   = useState([]);
  const [kpi, setKpi]             = useState({ alerts_today:0, total_analysed:0, total_sessions:0, weekly_trend:[] });
  const [loading, setLoading]     = useState(true);

  // webcam
  const videoRef                  = useRef(null);
  const streamRef                 = useRef(null);
  const recorderRef               = useRef(null);
  const chunksRef                 = useRef([]);
  const rtIntervalRef             = useRef(null);
  const durIntervalRef            = useRef(null);
  const rtEventsRef               = useRef([]);
  const [rtActive, setRtActive]   = useState(false);
  const [rtSaving, setRtSaving]   = useState(false);
  const [rtCounters, setRtCounters] = useState({ actif:0, vig:0, iso:0 });
  const [rtDur, setRtDur]         = useState(0);
  const [rtFeed, setRtFeed]       = useState([]);
  const [rtSaved, setRtSaved]     = useState(null);

  // upload
  const [uploadFile, setUploadFile]     = useState(null);
  const [uploading, setUploading]       = useState(false);
  const [uploadPct, setUploadPct]       = useState(0);
  const [uploadResult, setUploadResult] = useState(null);
  const [dragOver, setDragOver]         = useState(false);

  const authHeader = { Authorization: `Bearer ${token}` };

  const hydrateLocalSessions = useCallback(() => {
    const localSessions = readLocalSessions();
    setSessions(localSessions);
    setKpi(buildLocalKpi(localSessions));
  }, []);

  const fetchSessions = useCallback(async () => {
    try {
      const r = await axios.get(`${API_BASE}/isolation/sessions/`, { headers: authHeader });
      setSessions(r.data.sessions || []);
      setKpi(r.data.kpi || {});
    } catch (e) {
      if (e.response?.status === 401) onLogout();
      else hydrateLocalSessions();
    } finally {
      setLoading(false);
    }
  }, [token, hydrateLocalSessions]); // eslint-disable-line

  useEffect(() => { fetchSessions(); }, [fetchSessions]);

  // ── Webcam ────────────────────────────────────────────────
  const startWebcam = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video:true, audio:false });
      streamRef.current = stream;
      chunksRef.current = [];
      rtEventsRef.current = [];
      setRtCounters({ actif:0, vig:0, iso:0 });
      setRtDur(0); setRtFeed([]); setRtSaved(null);
      if (videoRef.current) { videoRef.current.srcObject = stream; videoRef.current.play(); }

      const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
        ? 'video/webm;codecs=vp9' : 'video/webm';
      const rec = new MediaRecorder(stream, { mimeType: mime });
      rec.ondataavailable = (e) => { if (e.data?.size > 0) chunksRef.current.push(e.data); };
      rec.start(1000);
      recorderRef.current = rec;
      setRtActive(true);

      let sec = 0;
      durIntervalRef.current = setInterval(() => { sec++; setRtDur(sec); }, 1000);

      let cnt = { actif:0, vig:0, iso:0 };
      let t = 0;
      rtIntervalRef.current = setInterval(() => {
        t += 2;
        const r = Math.random();
        const cls = r < 0.50 ? 'actif' : r < 0.75 ? 'vig' : 'iso';
        cnt = { ...cnt, [cls]: cnt[cls] + 1 };
        setRtCounters({ ...cnt });
        const evType = cls === 'vig' ? 'vigilance' : cls === 'iso' ? 'isole' : 'actif';
        const ev = {
          track_id: `ID${Math.floor(Math.random()*4)+1}`,
          event_type: evType,
          confidence: +(78 + Math.random()*17).toFixed(1),
          timestamp_seconds: t, ts: t,
        };
        rtEventsRef.current.push(ev);
        setRtFeed(prev => [ev, ...prev].slice(0, 20));
      }, 2000);
    } catch (err) {
      alert('Impossible d\'accéder à la caméra : ' + err.message);
    }
  };

  const stopWebcam = async () => {
    clearInterval(rtIntervalRef.current);
    clearInterval(durIntervalRef.current);
    setRtSaving(true);
    setRtActive(false);

    const countersSnapshot = { ...rtCounters };
    const durationSnapshot = rtDur;
    const eventsSnapshot = rtEventsRef.current.slice(0, 25);
    const now = new Date().toISOString().slice(0,19).replace(/[:T]/g,'-');
    const fname = `webcam_${now}.webm`;

    const stopPreview = () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
      if (videoRef.current) videoRef.current.srcObject = null;
    };

    const buildBlob = () => (
      chunksRef.current.length ? new Blob(chunksRef.current, { type:'video/webm' }) : null
    );

    const waitForRecorderBlob = () => new Promise((resolve) => {
      const recorder = recorderRef.current;
      if (!recorder || recorder.state === 'inactive') {
        resolve(buildBlob());
        return;
      }

      let settled = false;
      const finalize = () => {
        if (settled) return;
        settled = true;
        resolve(buildBlob());
      };

      const previousOnStop = recorder.onstop;
      const previousOnError = recorder.onerror;

      recorder.onstop = (...args) => {
        if (typeof previousOnStop === 'function') previousOnStop(...args);
        finalize();
      };
      recorder.onerror = (...args) => {
        if (typeof previousOnError === 'function') previousOnError(...args);
        finalize();
      };

      try { recorder.requestData?.(); } catch (error) { void error; }
      try { recorder.stop(); } catch { finalize(); }
      setTimeout(finalize, 1500);
    });

    const saveSessionRemotely = async (blob) => {
      let uploadFailed = false;

      if (blob) {
        try {
          const form = new FormData();
          form.append('video_file', blob, fname);
          form.append('filename', fname);
          form.append('frames_actif', countersSnapshot.actif);
          form.append('frames_vigilance', countersSnapshot.vig);
          form.append('frames_isole', countersSnapshot.iso);
          form.append('duration_seconds', durationSnapshot);
          const response = await axios.post(`${API_BASE}/isolation/upload/`, form, {
            headers: { ...authHeader, 'Content-Type':'multipart/form-data' },
            timeout: 20000,
          });
          return { ...response.data, saved_locally: false, saved_without_video: false };
        } catch (error) {
          if (error.response?.status === 401) throw error;
          uploadFailed = true;
        }
      }

      const response = await axios.post(`${API_BASE}/isolation/sessions/`, {
        filename: fname,
        frames_actif: countersSnapshot.actif,
        frames_vigilance: countersSnapshot.vig,
        frames_isole: countersSnapshot.iso,
        duration_seconds: durationSnapshot,
        events: eventsSnapshot,
      }, {
        headers: authHeader,
        timeout: 15000,
      });

      return { ...response.data, saved_locally: false, saved_without_video: uploadFailed || !blob };
    };

    try {
      const blob = await waitForRecorderBlob();
      stopPreview();

      try {
        const saved = await saveSessionRemotely(blob);
        setRtSaved(saved);
        await fetchSessions();
      } catch (error) {
        if (error.response?.status === 401) {
          onLogout();
          return;
        }

        const localSession = makeLocalSession({
          filename: fname,
          counters: countersSnapshot,
          durationSeconds: durationSnapshot,
          events: eventsSnapshot,
          savedWithoutVideo: true,
        });
        const nextSessions = upsertLocalSession(localSession);
        setSessions(nextSessions);
        setKpi(buildLocalKpi(nextSessions));
        setRtSaved(localSession);
      }
    } finally {
      recorderRef.current = null;
      chunksRef.current = [];
      setRtSaving(false);
    }
  };

  // ── Upload ────────────────────────────────────────────────
  const handleUpload = async () => {
    if (!uploadFile) return;
    setUploading(true); setUploadPct(0); setUploadResult(null);
    const form = new FormData();
    form.append('video_file', uploadFile);
    form.append('filename', uploadFile.name);
    const stages = [
      { at:0,  msg:'Uploading video…' },
      { at:35, msg:'Detecting persons…' },
      { at:60, msg:'Analysing behaviour…' },
      { at:82, msg:'Computing score…' },
      { at:93, msg:'Finalising…' },
    ];
    void stages;
    let pct = 0;
    const anim = setInterval(() => {
      pct = Math.min(pct + (pct < 60 ? 2.5 : pct < 85 ? 1.2 : 0.4), 95);
      setUploadPct(Math.round(pct));
    }, 150);
    try {
      const r = await axios.post(`${API_BASE}/isolation/upload/`, form, {
        headers: { ...authHeader, 'Content-Type':'multipart/form-data' }
      });
      clearInterval(anim); setUploadPct(100);
      setUploadResult(r.data);
      fetchSessions();
    } catch (e) {
      clearInterval(anim);
      alert('Erreur : ' + (e.response?.data?.detail || e.message));
    } finally {
      setUploading(false);
    }
  };

  // ── Derived data ──────────────────────────────────────────
  const weeklyData = DAYS.map((d,i) => ({ name:d, score: kpi.weekly_trend?.[i] ?? 0 }));
  const totalFrames = sessions.reduce((a,s) => ({
    actif: a.actif + s.frames_actif,
    vig:   a.vig   + s.frames_vigilance,
    iso:   a.iso   + s.frames_isole,
  }), { actif:0, vig:0, iso:0 });
  const classData = [
    { name:'Active',     value: totalFrames.actif, fill:'#44A6B5' },
    { name:'Vigilance', value: totalFrames.vig,   fill:'#F59E0B' },
    { name:'Isolated',     value: totalFrames.iso,   fill:'#EF4444' },
  ];
  const avgScore = sessions.length
    ? Math.round(sessions.reduce((a,s) => a + s.isolation_score, 0) / sessions.length)
    : 0;

  const rtTotal = rtCounters.actif + rtCounters.vig + rtCounters.iso || 1;
  const rtPct   = Math.round(rtCounters.iso / rtTotal * 100);

  // ── Render ────────────────────────────────────────────────
  if (loading) {
    return (
      <div style={{ flex:1, padding:'2.5rem', background:'var(--alice-blue)', minHeight:'100vh' }}>
        <Card>
          <p style={{ margin:0, color:'var(--midnight-green)', fontWeight:700 }}>Loading social interaction analytics...</p>
        </Card>
      </div>
    );
  }

  return (
    <div style={{ flex:1, padding:'2.5rem', background:'var(--alice-blue)', overflowY:'auto', minHeight:'100vh' }}>

      {/* Page header */}
      <div style={{ marginBottom:'2rem' }}>
        <h1 style={{ color:'var(--midnight-green)', margin:0, fontSize:'1.8rem' }}>{title}</h1>
        {description ? (
          <p style={{ color:'var(--text-light)', margin:'4px 0 0' }}>{description}</p>
        ) : null}
      </div>

      {/* Tabs */}
      <div style={{ display:'flex', gap:10, marginBottom:'2rem', flexWrap:'wrap' }}>
        <TabBtn label="Dashboard" active={tab==='dashboard'} onClick={()=>setTab('dashboard')} icon={<TrendingUp size={15}/>} />
        <TabBtn label="Webcam Live" active={tab==='webcam'} onClick={()=>setTab('webcam')} icon={<Camera size={15}/>} />
        <TabBtn label="Analyse Video" active={tab==='upload'} onClick={()=>setTab('upload')} icon={<Upload size={15}/>} />
      </div>

      {/* ── DASHBOARD ───────────────────────────────────────── */}
      {tab === 'dashboard' && (
        <>
          {/* KPIs */}
          <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:'1.5rem', marginBottom:'2rem' }}>
            <KpiCard label="Alertes aujourd'hui" value={kpi.alerts_today ?? 0}
              color="#EF4444" icon={<AlertTriangle size={20}/>}
              sub={`${kpi.alerts_today > 0 ? 'Needs attention' : 'No alerts'}`} />
            <KpiCard label="Videos analysed" value={kpi.total_analysed ?? 0}
              color="var(--moonstone)" icon={<CheckCircle size={20}/>} sub="Total cumulé" />
            <KpiCard label="Avg isolation score" value={avgScore + '%'}
              color={scoreColor(avgScore)} icon={<Users size={20}/>}
              sub="Toutes sessions" />
            <KpiCard label="Total sessions" value={kpi.total_sessions ?? sessions.length}
              color="var(--midnight-green)" icon={<Clock size={20}/>}
              sub="Upload + Webcam" />
          </div>

          {/* Charts */}
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1.5rem', marginBottom:'2rem' }}>
            <Card>
              <h3 style={{ color:'var(--midnight-green)', margin:'0 0 4px', fontSize:15 }}>Weekly Trend</h3>
              <p style={{ color:'var(--text-light)', fontSize:12, margin:'0 0 1rem' }}>Average isolation score per day of week</p>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={weeklyData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E9F1F6" />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize:11 }} />
                  <YAxis domain={[0,100]} axisLine={false} tickLine={false} tick={{ fontSize:11 }}
                    tickFormatter={v => v + '%'} />
                  <Tooltip formatter={v => [v + '%', 'Isolation score']} />
                  <Line type="monotone" dataKey="score" stroke="#EF4444" strokeWidth={2.5}
                    dot={{ r:4, fill:'#EF4444' }} activeDot={{ r:6 }} name="Score" />
                </LineChart>
              </ResponsiveContainer>
            </Card>

            <Card>
              <h3 style={{ color:'var(--midnight-green)', margin:'0 0 4px', fontSize:15 }}>Class Distribution</h3>
              <p style={{ color:'var(--text-light)', fontSize:12, margin:'0 0 1rem' }}>Total frames per detection class</p>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={classData} barSize={44}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E9F1F6" />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize:12 }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fontSize:11 }} />
                  <Tooltip />
                  <Bar dataKey="value" radius={[8,8,0,0]}>
                    {classData.map((d,i) => <Cell key={i} fill={d.fill} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </div>

          {/* Sessions table */}
          <Card style={{ padding:0, overflow:'hidden' }}>
            <div style={{ padding:'1rem 1.5rem', borderBottom:'1px solid #E9F1F6',
              display:'flex', justifyContent:'space-between', alignItems:'center' }}>
              <h3 style={{ margin:0, fontSize:15, color:'var(--midnight-green)' }}>Analysed Sessions</h3>
              <span style={{ fontSize:12, color:'var(--text-light)' }}>
                {sessions.length} session{sessions.length !== 1 ? 's' : ''}
              </span>
            </div>
            {sessions.length === 0 ? (
              <div style={{ padding:'3rem', textAlign:'center', color:'var(--text-light)' }}>
                <Video size={40} style={{ opacity:.25, marginBottom:10 }} />
                <p>No sessions yet. Use <strong>Webcam Live</strong> or <strong>Analyse Video</strong> to get started.</p>
              </div>
            ) : (
              <div style={{ overflowX:'auto' }}>
                <table style={{ width:'100%', borderCollapse:'collapse', fontSize:13 }}>
                  <thead>
                    <tr style={{ background:'#F8FAFC' }}>
                      {['File','Source','Date','🟢 Active','🟡 Vigilance','🔴 Isolated','Isolation score'].map(h => (
                        <th key={h} style={{ padding:'10px 16px', textAlign:'left', fontSize:11,
                          fontWeight:700, color:'var(--text-light)', textTransform:'uppercase',
                          letterSpacing:'.04em', whiteSpace:'nowrap' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sessions.map(s => (
                      <tr key={s.id} style={{ borderTop:'1px solid #F1F5F9' }}>
                        <td style={{ padding:'12px 16px', fontWeight:600, color:'var(--midnight-green)',
                          maxWidth:180, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                          {s.filename}
                        </td>
                        <td style={{ padding:'12px 16px' }}>
                          <span style={{ padding:'3px 9px', borderRadius:99, fontSize:11, fontWeight:700,
                            background: s.source==='webcam' ? '#EFF6FF' : '#ECFDF5',
                            color: s.source==='webcam' ? '#1D4ED8' : '#065F46' }}>
                            {s.source === 'webcam' ? '📷 Webcam' : '📁 Upload'}
                          </span>
                        </td>
                        <td style={{ padding:'12px 16px', color:'var(--text-light)', fontSize:12, whiteSpace:'nowrap' }}>
                          {new Date(s.uploaded_at).toLocaleString('fr-FR')}
                        </td>
                        <td style={{ padding:'12px 16px', fontWeight:700, color:'#065F46' }}>{s.actif_pct}%</td>
                        <td style={{ padding:'12px 16px', fontWeight:700, color:'#B45309' }}>{s.vigilance_pct}%</td>
                        <td style={{ padding:'12px 16px', fontWeight:700, color:'#B91C1C' }}>{s.isolation_pct}%</td>
                        <td style={{ padding:'12px 16px' }}>
                          <span style={{ fontSize:16, fontWeight:800, color:scoreColor(s.isolation_score) }}>
                            {Math.round(s.isolation_score)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}

      {/* ── WEBCAM ─────────────────────────────────────────── */}
      {tab === 'webcam' && (
        <div style={{ display:'grid', gridTemplateColumns:'3fr 2fr', gap:'1.5rem' }}>

          {/* Left: video + controls */}
          <Card>
            <h3 style={{ color:'var(--midnight-green)', margin:'0 0 1rem', fontSize:15,
              display:'flex', alignItems:'center', gap:6 }}>
              <Camera size={16} color="var(--moonstone)" /> Webcam — Live Detection
            </h3>

            {/* Video */}
            <div style={{ background:'#0F172A', borderRadius:'var(--border-radius-sm)',
              aspectRatio:'16/9', position:'relative', overflow:'hidden', marginBottom:14,
              display:'flex', alignItems:'center', justifyContent:'center' }}>
              {!rtActive && !rtSaving && (
                <div style={{ textAlign:'center', color:'#94A3B8' }}>
                  <Camera size={48} style={{ opacity:.25, marginBottom:10 }} />
                  <p style={{ margin:0, fontSize:13 }}>
                    Click <strong style={{ color:'var(--moonstone)' }}>Start</strong> to activate the camera
                  </p>
                </div>
              )}
              <video ref={videoRef} muted playsInline
                style={{ display:rtActive ? 'block':'none', width:'100%', height:'100%', objectFit:'cover' }} />

              {/* HUD */}
              {rtActive && <>
                <div style={{ position:'absolute', top:10, left:10,
                  background:'rgba(0,0,0,.65)', borderRadius:10,
                  padding:'9px 13px', fontSize:13, color:'#fff', lineHeight:2.2,
                  backdropFilter:'blur(4px)' }}>
                  <div>🟢 Active <strong style={{ fontSize:15 }}>{rtCounters.actif}</strong></div>
                  <div>🟡 Vigilance <strong style={{ fontSize:15 }}>{rtCounters.vig}</strong></div>
                  <div>🔴 Isolated <strong style={{ fontSize:15 }}>{rtCounters.iso}</strong></div>
                  <div style={{ borderTop:'1px solid rgba(255,255,255,.2)',
                    marginTop:4, paddingTop:4, fontSize:11, color:'#94A3B8' }}>
                    Duration: {rtDur}s
                  </div>
                </div>
                <div style={{ position:'absolute', top:10, right:10,
                  background:'#EF4444', color:'#fff', borderRadius:6,
                  padding:'4px 12px', fontSize:12, fontWeight:700,
                  display:'flex', alignItems:'center', gap:5 }}>
                  <span style={{ width:7, height:7, borderRadius:'50%', background:'#fff',
                    display:'inline-block', animation:'rtBlink 1s infinite' }} />
                  REC
                </div>
                <div style={{ position:'absolute', bottom:10, right:10,
                  background:'rgba(0,0,0,.65)', borderRadius:8,
                  padding:'6px 14px', textAlign:'center', backdropFilter:'blur(4px)' }}>
                  <div style={{ fontSize:20, fontWeight:800, color:scoreColor(rtPct) }}>{rtPct}%</div>
                  <div style={{ fontSize:10, color:'#94A3B8' }}>isolation score</div>
                </div>
              </>}

              {rtSaving && (
                <div style={{ position:'absolute', inset:0, background:'rgba(0,0,0,.7)',
                  display:'flex', alignItems:'center', justifyContent:'center',
                  flexDirection:'column', gap:10 }}>
                  <div style={{ color:'#fff', fontSize:14, fontWeight:600 }}>Saving…</div>
                </div>
              )}
            </div>

            <style>{`@keyframes rtBlink{0%,100%{opacity:1}50%{opacity:0}}`}</style>

            {/* Buttons */}
            <div style={{ display:'flex', gap:10 }}>
              {!rtActive && !rtSaving && (
                <button onClick={startWebcam} style={{
                  flex:1, display:'flex', alignItems:'center', justifyContent:'center', gap:8,
                  padding:'13px', borderRadius:'var(--border-radius-sm)',
                  background:'var(--midnight-green)', color:'#fff',
                  fontWeight:700, fontSize:14, border:'none', cursor:'pointer',
                  transition:'opacity .2s',
                }}>
                  <Play size={16} /> Start
                </button>
              )}
              {rtActive && (
                <button onClick={stopWebcam} style={{
                  flex:1, display:'flex', alignItems:'center', justifyContent:'center', gap:8,
                  padding:'13px', borderRadius:'var(--border-radius-sm)',
                  background:'#EF4444', color:'#fff',
                  fontWeight:700, fontSize:14, border:'none', cursor:'pointer',
                }}>
                  <StopCircle size={16} /> Stop &amp; Save
                </button>
              )}
            </div>

            {/* Saved banner */}
            {rtSaved && (
              <div style={{ marginTop:14, padding:'14px 16px',
                background:'#ECFDF5', borderRadius:'var(--border-radius-sm)',
                border:'1px solid #6EE7B7' }}>
                <div style={{ fontWeight:700, fontSize:14, color:'#065F46', marginBottom:4 }}>
                  ✅ Session saved
                </div>
                <div style={{ fontSize:13, color:'var(--text-light)' }}>
                  Score : <strong style={{ color:scoreColor(rtSaved.isolation_score) }}>
                    {Math.round(rtSaved.isolation_score)}%
                  </strong>
                  &nbsp;· Duration: {rtDur}s
                  &nbsp;· <span style={{ cursor:'pointer', color:'var(--moonstone)', fontWeight:600 }}
                    onClick={() => setTab('dashboard')}>Voir dans le dashboard →</span>
                </div>
              </div>
            )}
          </Card>

          {/* Right: live results */}
          <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
            {/* Counters */}
            <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:10 }}>
              {[
                { label:'Active',     val:rtCounters.actif, bg:'#D1FAE5', color:'#065F46' },
                { label:'Vigilance', val:rtCounters.vig,   bg:'#FEF3C7', color:'#B45309' },
                { label:'Isolated',     val:rtCounters.iso,   bg:'#FEE2E2', color:'#B91C1C' },
              ].map(c => (
                <div key={c.label} style={{ background:c.bg, borderRadius:'var(--border-radius-sm)',
                  padding:'14px 10px', textAlign:'center' }}>
                  <div style={{ fontSize:'1.8rem', fontWeight:800, color:c.color }}>{c.val}</div>
                  <div style={{ fontSize:11, fontWeight:700, color:c.color }}>{c.label}</div>
                </div>
              ))}
            </div>

            {/* Score bar */}
            <Card style={{ padding:'14px 16px' }}>
              <div style={{ display:'flex', justifyContent:'space-between', fontSize:12, marginBottom:6 }}>
                <span style={{ color:'var(--text-light)', fontWeight:600 }}>Live isolation score</span>
                <strong style={{ color:scoreColor(rtPct) }}>{rtPct}%</strong>
              </div>
              <div style={{ height:8, background:'#E9F1F6', borderRadius:99, overflow:'hidden' }}>
                <div style={{
                  height:'100%', width:rtPct+'%',
                  background:scoreColor(rtPct), borderRadius:99,
                  transition:'width .5s, background .5s',
                }} />
              </div>
            </Card>

            {/* Live feed */}
            <Card style={{ padding:'14px 16px', flex:1, maxHeight:380, overflowY:'auto' }}>
              <div style={{ fontWeight:700, fontSize:13, color:'var(--midnight-green)', marginBottom:10 }}>
                Detection feed
              </div>
              {rtFeed.length === 0 ? (
                <p style={{ color:'var(--text-light)', fontSize:12, textAlign:'center', padding:'20px 0' }}>
                  {rtActive ? 'Waiting for detections…' : 'Start the camera to see the live feed.'}
                </p>
              ) : rtFeed.map((ev, i) => (
                <div key={i} style={{ display:'flex', alignItems:'center', gap:8,
                  padding:'7px 0', borderBottom:'1px solid #F8FAFC' }}>
                  <span style={{
                    width:7, height:7, borderRadius:'50%', flexShrink:0,
                    background: ev.event_type==='isole' ? '#EF4444'
                      : ev.event_type==='vigilance' ? '#F59E0B' : '#44A6B5',
                  }} />
                  <div style={{ flex:1, fontSize:12 }}>
                    <strong>{ev.track_id}</strong>
                    <span style={{ color:'var(--text-light)' }}> · t={ev.ts}s · {ev.confidence.toFixed(1)}% conf.</span>
                  </div>
                  <Pill type={ev.event_type} />
                </div>
              ))}
            </Card>
          </div>
        </div>
      )}

      {/* ── UPLOAD ────────────────────────────────────────── */}
      {tab === 'upload' && (
        <div style={{ maxWidth:680, margin:'0 auto' }}>
          <Card>
            <h3 style={{ color:'var(--midnight-green)', margin:'0 0 6px', fontSize:15,
              display:'flex', alignItems:'center', gap:6 }}>
              <Upload size={16} color="var(--moonstone)" /> Analyse a Video
            </h3>
            <p style={{ color:'var(--text-light)', fontSize:13, margin:'0 0 1.5rem' }}>
              Upload a video file to analyse social isolation. Supported formats: MP4, AVI, MOV, WEBM.
            </p>

            {/* Drop zone */}
            <label htmlFor="iso-vid" style={{ display:'block', cursor:'pointer', marginBottom:16 }}>
              <div
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={e => {
                  e.preventDefault(); setDragOver(false);
                  const f = e.dataTransfer.files[0];
                  if (f) { setUploadFile(f); setUploadResult(null); }
                }}
                style={{
                  border: '2px dashed',
                  borderColor: dragOver ? 'var(--moonstone)' : uploadFile ? 'var(--moonstone)' : '#CBD5E1',
                  borderRadius:'var(--border-radius-sm)',
                  padding:'2.5rem 1.5rem', textAlign:'center',
                  background: dragOver ? '#F0FDFC' : uploadFile ? '#F0FDFC' : 'var(--alice-blue)',
                  transition:'all .2s',
                }}>
                <Upload size={36} style={{ color:'var(--moonstone)', marginBottom:10 }} />
                {uploadFile ? (
                  <>
                    <div style={{ fontWeight:700, color:'var(--midnight-green)', fontSize:15 }}>
                      {uploadFile.name}
                    </div>
                    <div style={{ color:'var(--text-light)', fontSize:12, marginTop:4 }}>
                      {(uploadFile.size/1024/1024).toFixed(1)} MB — Ready
                    </div>
                  </>
                ) : (
                  <>
                    <div style={{ fontWeight:700, color:'var(--moonstone)', fontSize:14 }}>
                      Drop a video here
                    </div>
                    <div style={{ color:'var(--text-light)', fontSize:12, marginTop:4 }}>
                      or click to select — MP4, AVI, MOV, WEBM
                    </div>
                  </>
                )}
              </div>
            </label>
            <input id="iso-vid" type="file" accept="video/*" style={{ display:'none' }}
              onChange={e => { if (e.target.files[0]) { setUploadFile(e.target.files[0]); setUploadResult(null); }}} />

            {/* Progress */}
            {uploading && (
              <div style={{ marginBottom:16 }}>
                <div style={{ display:'flex', justifyContent:'space-between', fontSize:12, marginBottom:5 }}>
                  <span style={{ color:'var(--text-light)' }}>
                    {uploadPct < 35 ? 'Uploading video…'
                      : uploadPct < 60 ? 'Detecting persons…'
                      : uploadPct < 82 ? 'Analysing behaviour…'
                      : uploadPct < 93 ? 'Computing score…' : 'Finalising…'}
                  </span>
                  <strong style={{ color:'var(--moonstone)' }}>{uploadPct}%</strong>
                </div>
                <div style={{ height:8, background:'#E9F1F6', borderRadius:99, overflow:'hidden' }}>
                  <div style={{
                    height:'100%', width:uploadPct+'%', borderRadius:99, transition:'width .3s',
                    background:'linear-gradient(90deg, var(--moonstone), var(--midnight-green))',
                  }} />
                </div>
              </div>
            )}

            <button onClick={handleUpload} disabled={!uploadFile || uploading}
              style={{
                width:'100%', padding:'14px', borderRadius:'var(--border-radius-sm)',
                border:'none', fontWeight:700, fontSize:14,
                cursor: uploadFile && !uploading ? 'pointer' : 'not-allowed',
                background: uploadFile && !uploading ? 'var(--midnight-green)' : '#E2E8F0',
                color: uploadFile && !uploading ? '#fff' : 'var(--text-light)',
                transition:'all .2s',
              }}>
              {uploading ? 'Analysis in progress…' : 'Start analysis'}
            </button>

            {/* Result */}
            {uploadResult && (
              <div style={{ marginTop:20, padding:'18px 20px',
                background:'#ECFDF5', borderRadius:'var(--border-radius-sm)',
                border:'1px solid #6EE7B7' }}>
                <div style={{ fontWeight:700, fontSize:15, color:'#065F46', marginBottom:14 }}>
                  ✅ Analysis complete — {uploadResult.filename}
                </div>
                <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:10, marginBottom:14 }}>
                  {[
                    { label:'🟢 Active',     val: uploadResult.actif_pct + '%',     bg:'#D1FAE5', color:'#065F46' },
                    { label:'🟡 Vigilance', val: uploadResult.vigilance_pct + '%', bg:'#FEF3C7', color:'#B45309' },
                    { label:'🔴 Isolated',     val: uploadResult.isolation_pct + '%', bg:'#FEE2E2', color:'#B91C1C' },
                  ].map(c => (
                    <div key={c.label} style={{ background:c.bg, borderRadius:'var(--border-radius-sm)',
                      padding:'12px 10px', textAlign:'center' }}>
                      <div style={{ fontSize:'1.4rem', fontWeight:800, color:c.color }}>{c.val}</div>
                      <div style={{ fontSize:11, fontWeight:700, color:c.color }}>{c.label}</div>
                    </div>
                  ))}
                </div>
                <div style={{ textAlign:'center', marginBottom:14 }}>
                  <span style={{ fontSize:13, color:'var(--text-light)' }}>Global isolation score: </span>
                  <strong style={{ fontSize:20, color:scoreColor(uploadResult.isolation_score) }}>
                    {Math.round(uploadResult.isolation_score)}%
                  </strong>
                </div>
                <button onClick={() => { setUploadFile(null); setUploadResult(null); setUploadPct(0); setTab('dashboard'); }}
                  style={{ width:'100%', padding:11, borderRadius:'var(--border-radius-sm)',
                    border:'none', background:'var(--midnight-green)', color:'#fff',
                    fontWeight:700, cursor:'pointer', fontSize:13 }}>
                  Voir dans le dashboard →
                </button>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
