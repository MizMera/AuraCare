import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { Activity, AlertTriangle, CheckCircle, Utensils, TrendingUp, Clock } from 'lucide-react';

const API_HOST = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';
const API_BASE = `http://${API_HOST}:8000/api`;

const Card = ({ children, style }) => (
  <div style={{
    backgroundColor: 'white', borderRadius: 16,
    boxShadow: '0 2px 12px rgba(15,23,42,.07)',
    padding: '1.5rem', ...style,
  }}>{children}</div>
);

const GI_COLORS = {
  'High':  { bg: '#FEE2E2', color: '#B91C1C' },
  'Medium':  { bg: '#FEF3C7', color: '#B45309' },
  'Low': { bg: '#D1FAE5', color: '#065F46' },
  'None':    { bg: '#F1F5F9', color: '#475569' },
};

const CLASS_META = {
  0: { label: 'Hypoglycemia',      color: '#3B82F6', bg: '#EFF6FF', icon: '↓',  border: '#BFDBFE' },
  1: { label: 'Normal',           color: '#10B981', bg: '#ECFDF5', icon: '✓',  border: '#6EE7B7' },
  2: { label: 'Pre-Hyperglycemia', color: '#F59E0B', bg: '#FFFBEB', icon: '!',  border: '#FDE68A' },
  3: { label: 'Hyperglycemia',     color: '#EF4444', bg: '#FFF5F5', icon: '↑',  border: '#FECACA' },
};

function GlucoseMeter({ value }) {
  const pct = Math.min(Math.max((value / 350) * 100, 0), 100);
  let barColor = '#10B981';
  if (value < 70)        barColor = '#3B82F6';
  else if (value >= 200) barColor = '#EF4444';
  else if (value >= 140) barColor = '#F59E0B';

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#64748B', marginBottom: 4 }}>
        <span>0</span><span>70</span><span>140</span><span>200</span><span>350+</span>
      </div>
      <div style={{ height: 18, background: '#F1F5F9', borderRadius: 99, overflow: 'hidden', position: 'relative' }}>
        {/* zones de couleur */}
        <div style={{ position:'absolute', left:'0%',   width:'20%',  height:'100%', background:'#BFDBFE', opacity:.5 }} />
        <div style={{ position:'absolute', left:'20%',  width:'40%',  height:'100%', background:'#BBF7D0', opacity:.5 }} />
        <div style={{ position:'absolute', left:'60%',  width:'17%',  height:'100%', background:'#FDE68A', opacity:.5 }} />
        <div style={{ position:'absolute', left:'77%',  width:'23%',  height:'100%', background:'#FECACA', opacity:.5 }} />
        {/* curseur */}
        <div style={{
          position: 'absolute', top: 0, left: `${pct}%`,
          transform: 'translateX(-50%)',
          width: 4, height: '100%',
          background: barColor, borderRadius: 2,
          transition: 'left .5s',
        }} />
      </div>
      <div style={{ textAlign: 'center', marginTop: 6, fontSize: 28, fontWeight: 900, color: barColor }}>
        {value} <span style={{ fontSize: 13, fontWeight: 600, color: '#94A3B8' }}>mg/dL</span>
      </div>
    </div>
  );
}

export default function DiabetesMonitor({ token, onLogout }) {
  const authHeader = { Authorization: `Bearer ${token}` };

  const [residents, setResidents]         = useState([]);
  const [selectedId, setSelectedId]       = useState(null);
  const [form, setForm]                   = useState({
    blood_glucose_level: '',
    HbA1c_level: '',
    bmi: '',
    notes: '',
  });
  const [result, setResult]               = useState(null);
  const [history, setHistory]             = useState([]);
  const [loading, setLoading]             = useState(false);
  const [modelStatus, setModelStatus]     = useState(null);
  const [savingReading, setSavingReading] = useState(false);

  // Load diabetic residents
  const fetchResidents = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/residents/`, { headers: authHeader });
      setResidents(Array.isArray(res.data) ? res.data : []);
    } catch (e) { if (e.response?.status === 401) onLogout(); }
  }, [token]); // eslint-disable-line

  // Model status
  const fetchModelStatus = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/diabetes/status/`, { headers: authHeader });
      setModelStatus(res.data);
    } catch { /* silencieux */ }
  }, [token]); // eslint-disable-line

  // Resident history
  const fetchHistory = useCallback(async (residentId) => {
    if (!residentId) return;
    try {
      const res = await axios.get(`${API_BASE}/diabetes/history/${residentId}/`, { headers: authHeader });
      setHistory(res.data.readings || []);
    } catch { setHistory([]); }
  }, [token]); // eslint-disable-line

  useEffect(() => { fetchResidents(); fetchModelStatus(); }, [fetchResidents, fetchModelStatus]);
  useEffect(() => { if (selectedId) { fetchHistory(selectedId); setResult(null); } }, [selectedId, fetchHistory]);

  const handlePredict = async () => {
    if (!selectedId || !form.blood_glucose_level) return;
    setLoading(true);
    setResult(null);
    try {
      const payload = {
        resident_id:         selectedId,
        blood_glucose_level: parseFloat(form.blood_glucose_level),
        ...(form.HbA1c_level && { HbA1c_level: parseFloat(form.HbA1c_level) }),
        ...(form.bmi         && { bmi:         parseFloat(form.bmi) }),
      };
      const res = await axios.post(`${API_BASE}/diabetes/predict/`, payload, { headers: authHeader });
      setResult(res.data);
    } catch (e) {
      if (e.response?.status === 401) onLogout();
    } finally {
      setLoading(false);
    }
  };

  const handleSaveReading = async () => {
    if (!selectedId || !form.blood_glucose_level) return;
    setSavingReading(true);
    try {
      await axios.post(
        `${API_BASE}/diabetes/history/${selectedId}/`,
        {
          blood_glucose_level: parseFloat(form.blood_glucose_level),
          notes: form.notes,
          ...(form.HbA1c_level && { HbA1c_level: parseFloat(form.HbA1c_level) }),
        },
        { headers: authHeader },
      );
      fetchHistory(selectedId);
    } catch { /* silencieux */ } finally {
      setSavingReading(false);
    }
  };

  const selectedResident = residents.find(r => r.id === selectedId);
  const glucoseValue     = parseFloat(form.blood_glucose_level) || 0;
  const classIdx         = glucoseValue < 70 ? 0 : glucoseValue < 140 ? 1 : glucoseValue < 200 ? 2 : 3;
  const classMeta        = CLASS_META[classIdx];

  // Historical data for chart
  const chartData = [...history].reverse().map((r, i) => ({
    name:  new Date(r.measured_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }),
    value: r.value,
    class: r.class,
  }));

  return (
    <div style={{ flex: 1, padding: '2.5rem', background: 'var(--alice-blue)', overflowY: 'auto', minHeight: '100vh' }}>

      {/* Header */}
      <div style={{ marginBottom: '2rem' }}>
        <h1 style={{ color: 'var(--midnight-green)', margin: 0, fontSize: '1.8rem', display: 'flex', alignItems: 'center', gap: 10 }}>
          <Activity size={26} /> Glucose Monitoring — Diabetes
        </h1>
        <p style={{ color: 'var(--text-light)', margin: '4px 0 0', fontSize: 14 }}>
          Measure blood glucose and get AI-powered personalized dietary recommendations.
        </p>
      </div>

      {/* Model status */}
      {modelStatus?.model_ready && (
        <div style={{
          marginBottom: '1.5rem', padding: '12px 16px', borderRadius: 12,
          background: '#ECFDF5',
          border: '1px solid #6EE7B7',
          display: 'flex', alignItems: 'center', gap: 10, fontSize: 13,
        }}>
          <CheckCircle size={16} color="#10B981" /> <strong style={{ color: '#065F46' }}>LSTM Model active</strong> — Deep learning predictions
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.4fr', gap: '1.5rem', alignItems: 'start' }}>

        {/* ── Left column: input ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>

          {/* Resident selection */}
          <Card>
            <div style={{ fontWeight: 800, color: 'var(--midnight-green)', marginBottom: 12, fontSize: 15 }}>
              Select resident
            </div>
            <div style={{ display: 'grid', gap: 8, maxHeight: 220, overflowY: 'auto' }}>
              {residents.map(r => (
                <button key={r.id} onClick={() => setSelectedId(r.id)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
                    borderRadius: 10, border: '2px solid',
                    borderColor: selectedId === r.id ? 'var(--moonstone)' : '#E2E8F0',
                    background:  selectedId === r.id ? '#F0FDFC' : 'white',
                    cursor: 'pointer', textAlign: 'left', transition: 'all .15s',
                  }}>
                  <div style={{
                    width: 38, height: 38, borderRadius: '50%', flexShrink: 0, overflow: 'hidden',
                    background: '#F1F5F9', border: '2px solid #E2E8F0',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    {r.photo_url
                      ? <img src={r.photo_url} alt={r.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      : <span style={{ fontSize: 16 }}>?</span>
                    }
                  </div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--midnight-green)' }}>{r.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-light)' }}>Room {r.room_number} · {r.age} yrs</div>
                  </div>
                </button>
              ))}
            </div>
          </Card>

          {/* Measurements input */}
          <Card>
            <div style={{ fontWeight: 800, color: 'var(--midnight-green)', marginBottom: 14, fontSize: 15 }}>
              Enter measurements
            </div>

            {/* Main glucose */}
            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-light)', display: 'block', marginBottom: 5 }}>
                Blood glucose (mg/dL) *
              </label>
              <input
                type="number" min="0" max="600" step="1"
                value={form.blood_glucose_level}
                onChange={e => setForm(f => ({ ...f, blood_glucose_level: e.target.value }))}
                placeholder="ex : 145"
                style={{
                  width: '100%', padding: '11px 14px', borderRadius: 10,
                  border: '2px solid', borderColor: form.blood_glucose_level ? classMeta.border : '#E2E8F0',
                  fontSize: 16, fontWeight: 700, outline: 'none', boxSizing: 'border-box',
                  color: form.blood_glucose_level ? classMeta.color : '#334155',
                  background: form.blood_glucose_level ? classMeta.bg : 'white',
                  transition: 'all .2s',
                }}
              />
              {/* Real-time indicator */}
              {form.blood_glucose_level && (
                <div style={{
                  marginTop: 6, padding: '5px 10px', borderRadius: 8,
                  background: classMeta.bg, border: `1px solid ${classMeta.border}`,
                  fontSize: 12, fontWeight: 700, color: classMeta.color,
                  display: 'flex', alignItems: 'center', gap: 6,
                }}>
                  <span>{classMeta.icon}</span> {classMeta.label}
                </div>
              )}
            </div>

            {/* HbA1c and BMI side by side */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
              {[
                { key: 'HbA1c_level', label: 'HbA1c (%)', placeholder: 'e.g. 7.2', step: '0.1' },
                { key: 'bmi',         label: 'BMI (kg/m²)', placeholder: 'e.g. 28.5', step: '0.1' },
              ].map(f => (
                <div key={f.key}>
                  <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-light)', display: 'block', marginBottom: 4 }}>
                    {f.label}
                  </label>
                  <input
                    type="number" step={f.step} placeholder={f.placeholder}
                    value={form[f.key]}
                    onChange={e => setForm(fv => ({ ...fv, [f.key]: e.target.value }))}
                    style={{
                      width: '100%', padding: '9px 11px', borderRadius: 9,
                      border: '1.5px solid #E2E8F0', fontSize: 13,
                      outline: 'none', boxSizing: 'border-box',
                    }}
                  />
                </div>
              ))}
            </div>

            {/* Notes */}
            <div style={{ marginBottom: 14 }}>
              <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-light)', display: 'block', marginBottom: 4 }}>
                Notes (optionnel)
              </label>
              <textarea
                rows={2} placeholder="before meal, after exercise..."
                value={form.notes}
                onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                style={{
                  width: '100%', padding: '9px 11px', borderRadius: 9,
                  border: '1.5px solid #E2E8F0', fontSize: 12, resize: 'none',
                  outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit',
                }}
              />
            </div>

            {/* Buttons */}
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={handlePredict}
                disabled={!selectedId || !form.blood_glucose_level || loading}
                style={{
                  flex: 2, padding: '12px', borderRadius: 10, border: 'none',
                  fontWeight: 800, fontSize: 14, cursor: 'pointer',
                  background: (!selectedId || !form.blood_glucose_level || loading) ? '#E2E8F0' : 'var(--midnight-green)',
                  color:      (!selectedId || !form.blood_glucose_level || loading) ? '#94A3B8' : 'white',
                  transition: 'all .2s',
                }}
              >
                {loading ? 'Analyzing…' : 'Analyze & Recommend'}
              </button>
              <button
                onClick={handleSaveReading}
                disabled={!selectedId || !form.blood_glucose_level || savingReading}
                style={{
                  flex: 1, padding: '12px', borderRadius: 10,
                  border: '1.5px solid #E2E8F0', fontWeight: 700, fontSize: 13,
                  cursor: 'pointer', background: 'white', color: 'var(--midnight-green)',
                }}
              >
                {savingReading ? '…' : 'Save'}
              </button>
            </div>
          </Card>

          {/* History chart */}
          {history.length > 0 && (
            <Card>
              <div style={{ fontWeight: 800, color: 'var(--midnight-green)', marginBottom: 12, fontSize: 14, display: 'flex', alignItems: 'center', gap: 7 }}>
                <TrendingUp size={15} /> Glucose History
              </div>
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                  <XAxis dataKey="name" tick={{ fontSize: 9 }} />
                  <YAxis domain={[40, 300]} tick={{ fontSize: 9 }} />
                  <Tooltip
                    formatter={(v) => [`${v} mg/dL`, 'Blood Glucose']}
                    contentStyle={{ borderRadius: 8, fontSize: 12 }}
                  />
                  <ReferenceLine y={70}  stroke="#3B82F6" strokeDasharray="4 4" label={{ value:'Hypo', fontSize:9, fill:'#3B82F6' }} />
                  <ReferenceLine y={140} stroke="#F59E0B" strokeDasharray="4 4" label={{ value:'140', fontSize:9, fill:'#F59E0B' }} />
                  <ReferenceLine y={200} stroke="#EF4444" strokeDasharray="4 4" label={{ value:'Hyper', fontSize:9, fill:'#EF4444' }} />
                  <Line
                    type="monotone" dataKey="value" stroke="var(--midnight-green)"
                    strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          )}
        </div>

        {/* ── Right column: results ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>

          {result ? (
            <>
              {/* Glucose result */}
              <Card style={{ border: '2px solid', borderColor: CLASS_META[result.glucose_class]?.border }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
                  <div>
                    <div style={{ fontWeight: 800, fontSize: 16, color: 'var(--midnight-green)' }}>
                      {result.resident_name}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-light)', marginTop: 2 }}>
                      <Clock size={11} style={{ verticalAlign: 'middle' }} /> {new Date().toLocaleString('fr-FR')}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    {result.confidence && (
                      <div style={{ fontSize: 11, color: 'var(--text-light)' }}>
                        AI Confidence : <strong>{result.confidence}%</strong>
                      </div>
                    )}
                    <div style={{ fontSize: 11, color: 'var(--text-light)' }}>
                      Model: {result.model_used}
                    </div>
                  </div>
                </div>

                {/* Glucose gauge */}
                <GlucoseMeter value={result.blood_glucose} />

                {/* Class badge */}
                <div style={{
                  marginTop: 14, padding: '10px 14px', borderRadius: 10,
                  background: CLASS_META[result.glucose_class]?.bg,
                  border: '1.5px solid', borderColor: CLASS_META[result.glucose_class]?.border,
                  display: 'flex', alignItems: 'center', gap: 10,
                }}>
                  <span style={{ fontSize: 22 }}>{CLASS_META[result.glucose_class]?.icon}</span>
                  <div>
                    <div style={{ fontWeight: 800, fontSize: 15, color: CLASS_META[result.glucose_class]?.color }}>
                      {result.class_label}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-light)' }}>{result.class_range}</div>
                  </div>
                  {result.recommendation?.urgent && (
                    <div style={{
                      marginLeft: 'auto', padding: '4px 10px', borderRadius: 99,
                      background: '#FEE2E2', color: '#B91C1C', fontWeight: 800, fontSize: 11,
                      display: 'flex', alignItems: 'center', gap: 4,
                    }}>
                      <AlertTriangle size={11} /> URGENT
                    </div>
                  )}
                </div>
              </Card>

              {/* Dietary recommendations */}
              {result.recommendation && (
                <Card>
                  <div style={{ fontWeight: 800, fontSize: 15, color: 'var(--midnight-green)', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Utensils size={16} /> Dietary Recommendations
                  </div>
                  <p style={{ fontSize: 13, color: 'var(--text-light)', margin: '0 0 14px' }}>
                    {result.recommendation.title}
                  </p>

                  {/* Recommended foods */}
                  <div style={{ marginBottom: 14 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--midnight-green)', marginBottom: 8 }}>
                      Recommended foods
                    </div>
                    <div style={{ display: 'grid', gap: 7 }}>
                      {result.recommendation.foods?.map((food, i) => {
                        const gi = GI_COLORS[food.gi] || GI_COLORS['None'];
                        return (
                          <div key={i} style={{
                            display: 'flex', alignItems: 'center', gap: 10,
                            padding: '9px 12px', borderRadius: 10,
                            background: '#FAFAFA', border: '1px solid #F1F5F9',
                          }}>
                            <span style={{ fontSize: 20, flexShrink: 0 }}>{food.icon}</span>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--midnight-green)' }}>
                                {food.name}
                              </div>
                              <div style={{ fontSize: 11, color: 'var(--text-light)' }}>
                                Carbs: {food.carbs}
                              </div>
                            </div>
                            <span style={{
                              padding: '2px 8px', borderRadius: 99, fontSize: 10, fontWeight: 800,
                              background: gi.bg, color: gi.color, flexShrink: 0,
                            }}>
                              GI {food.gi}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Advice */}
                  <div style={{
                    padding: '10px 13px', borderRadius: 10,
                    background: '#F0FDFA', border: '1px solid #99F6E4',
                    fontSize: 12, color: '#0F766E', fontWeight: 600, marginBottom: 12,
                  }}>
                    {result.recommendation.advice}
                  </div>

                  {/* Foods to avoid */}
                  {result.recommendation.avoid?.length > 0 && (
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: '#B91C1C', marginBottom: 7 }}>
                        To avoid
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                        {result.recommendation.avoid.map((item, i) => (
                          <span key={i} style={{
                            padding: '4px 10px', borderRadius: 99, fontSize: 11,
                            background: '#FEF2F2', color: '#B91C1C',
                            border: '1px solid #FECACA', fontWeight: 600,
                          }}>
                            {item}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </Card>
              )}
            </>
          ) : (
            /* Initial state */
            <Card style={{ textAlign: 'center', padding: '3rem 2rem' }}>
              <div style={{ fontSize: 64, marginBottom: 12, color: 'var(--moonstone)' }}><Activity size={56} /></div>
              <div style={{ fontWeight: 800, fontSize: 16, color: 'var(--midnight-green)', marginBottom: 8 }}>
                Smart glucose monitoring
              </div>
              <p style={{ color: 'var(--text-light)', fontSize: 13, maxWidth: 300, margin: '0 auto 16px' }}>
                Select a resident, enter their blood glucose level and get an AI analysis with personalized dietary recommendations.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, maxWidth: 280, margin: '0 auto' }}>
                {Object.entries(CLASS_META).map(([k, v]) => (
                  <div key={k} style={{
                    padding: '8px 12px', borderRadius: 10,
                    background: v.bg, border: `1px solid ${v.border}`,
                    fontSize: 12, fontWeight: 700, color: v.color,
                    textAlign: 'left',
                  }}>
                    {v.icon} {v.label}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Recent history */}
          {history.length > 0 && (
            <Card style={{ padding: '1.25rem' }}>
              <div style={{ fontWeight: 800, fontSize: 14, color: 'var(--midnight-green)', marginBottom: 10 }}>
              Recent readings
              </div>
              <div style={{ display: 'grid', gap: 6 }}>
                {history.slice(0, 5).map(r => {
                  const m = CLASS_META[r.class] || CLASS_META[1];
                  return (
                    <div key={r.id} style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                      padding: '8px 11px', borderRadius: 9,
                      background: m.bg, border: `1px solid ${m.border}`,
                    }}>
                      <span style={{ fontWeight: 800, fontSize: 15, color: m.color, flexShrink: 0 }}>
                        {r.value} mg/dL
                      </span>
                      <span style={{ fontSize: 11, fontWeight: 700, color: m.color }}>{m.label}</span>
                      <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-light)' }}>
                        {new Date(r.measured_at).toLocaleString('en-GB', { day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit' })}
                      </span>
                    </div>
                  );
                })}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
