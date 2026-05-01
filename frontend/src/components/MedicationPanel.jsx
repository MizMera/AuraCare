import { useEffect, useState } from 'react';
import axios from 'axios';
import { Pill, AlertCircle, CheckCircle2, Clock, ChevronDown, ChevronUp, Plus, X } from 'lucide-react';

const API_HOST = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';
const API_BASE = `http://${API_HOST}:8000/api`;

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

const RISK_STYLES = {
  high:   { bg: '#FEE2E2', border: '#DC2626', text: '#7F1D1D', badge: '#EF4444', label: 'HIGH RISK' },
  medium: { bg: '#FFF7ED', border: '#D97706', text: '#78350F', badge: '#F59E0B', label: 'MEDIUM RISK' },
  low:    { bg: '#ECFDF5', border: '#059669', text: '#064E3B', badge: '#10B981', label: 'LOW RISK' },
};

// ─── Log Form Modal ────────────────────────────────────────────────────────────
function LogMedicationModal({ resident, token, onClose, onSaved }) {
  const [medications, setMedications] = useState([]);
  const [form, setForm] = useState({
    medication_id: '',
    status: 'taken',
    scheduled_at: new Date().toISOString().slice(0, 16),
    actual_taken_at: new Date().toISOString().slice(0, 16),
    notes: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    axios.get(`${API_BASE}/medication/residents/${resident.id}/`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then(res => setMedications(res.data)).catch(() => setError('Could not load medications.'));
  }, [resident.id, token]);

  const handleSubmit = async () => {
    if (!form.medication_id) { setError('Please select a medication.'); return; }
    setSaving(true);
    setError('');
    try {
      await axios.post(`${API_BASE}/medication/log/`, {
        resident_id: resident.id,
        medication_id: form.medication_id,
        status: form.status,
        scheduled_at: form.scheduled_at,
        actual_taken_at: form.status === 'taken' || form.status === 'late' ? form.actual_taken_at : null,
        notes: form.notes,
      }, { headers: { Authorization: `Bearer ${token}` } });
      onSaved();
      onClose();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to save log.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.4)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}>
      <div style={{ backgroundColor: 'white', borderRadius: '20px', padding: '2rem', width: '100%', maxWidth: '480px', boxShadow: '0 20px 60px rgba(0,0,0,0.2)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <div>
            <h3 style={{ margin: 0, color: 'var(--midnight-green)' }}>Log Medication</h3>
            <p style={{ margin: '0.25rem 0 0', color: 'var(--text-light)', fontSize: '0.9rem' }}>{resident.name} — Room {resident.room_number}</p>
          </div>
          <button onClick={onClose} style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--text-light)' }}>
            <X size={20} />
          </button>
        </div>

        <div style={{ display: 'grid', gap: '1rem' }}>
          <label>
            <span style={formLabelStyle}>Medication</span>
            <select
              value={form.medication_id}
              onChange={e => setForm(f => ({ ...f, medication_id: e.target.value }))}
              style={formInputStyle}
            >
              <option value="">Select medication...</option>
              {medications.map(m => (
                <option key={m.id} value={m.id}>{m.name} {m.dosage} — {m.scheduled_time}</option>
              ))}
            </select>
          </label>

          <label>
            <span style={formLabelStyle}>Status</span>
            <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))} style={formInputStyle}>
              <option value="taken">✅ Taken</option>
              <option value="missed">❌ Missed</option>
              <option value="late">⏰ Late</option>
              <option value="refused">🚫 Refused</option>
            </select>
          </label>

          <label>
            <span style={formLabelStyle}>Scheduled At</span>
            <input type="datetime-local" value={form.scheduled_at} onChange={e => setForm(f => ({ ...f, scheduled_at: e.target.value }))} style={formInputStyle} />
          </label>

          {(form.status === 'taken' || form.status === 'late') && (
            <label>
              <span style={formLabelStyle}>Actually Taken At</span>
              <input type="datetime-local" value={form.actual_taken_at} onChange={e => setForm(f => ({ ...f, actual_taken_at: e.target.value }))} style={formInputStyle} />
            </label>
          )}

          <label>
            <span style={formLabelStyle}>Notes (optional)</span>
            <input placeholder="Any observations..." value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} style={formInputStyle} />
          </label>

          {error && (
            <div style={{ backgroundColor: '#FEF2F2', color: '#B91C1C', padding: '0.75rem 1rem', borderRadius: '10px', fontSize: '0.9rem', fontWeight: 600 }}>
              {error}
            </div>
          )}

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button
              onClick={handleSubmit}
              disabled={saving}
              style={{ flex: 1, border: 'none', borderRadius: '12px', padding: '12px', backgroundColor: 'var(--midnight-green)', color: 'white', fontWeight: 700, cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.7 : 1 }}
            >
              {saving ? 'Saving...' : 'Save Log'}
            </button>
            <button
              onClick={onClose}
              style={{ border: '1px solid #D7E3EA', borderRadius: '12px', padding: '12px 20px', backgroundColor: 'white', color: 'var(--midnight-green)', fontWeight: 700, cursor: 'pointer' }}
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Resident Risk Row ─────────────────────────────────────────────────────────
function ResidentRiskRow({ score, token, onLogSaved }) {
  const [expanded, setExpanded] = useState(false);
  const [showLogModal, setShowLogModal] = useState(false);
  const [history, setHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const style = RISK_STYLES[score.risk_level] || RISK_STYLES.low;

  const loadHistory = async () => {
    if (history.length > 0) return; // already loaded
    setLoadingHistory(true);
    try {
      const res = await axios.get(`${API_BASE}/medication/log/${score.resident_id}/?days=7`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setHistory(res.data);
    } catch {
      // silently fail
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleExpand = () => {
    if (!expanded) loadHistory();
    setExpanded(e => !e);
  };

  return (
    <>
      {showLogModal && (
        <LogMedicationModal
          resident={{ id: score.resident_id, name: score.resident_name, room_number: score.room_number }}
          token={token}
          onClose={() => setShowLogModal(false)}
          onSaved={onLogSaved}
        />
      )}

      <div style={{ border: `1px solid ${style.border}`, borderRadius: '16px', overflow: 'hidden', backgroundColor: 'white' }}>
        {/* Main row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '1rem 1.25rem', flexWrap: 'wrap' }}>
          {/* Risk color bar */}
          <div style={{ width: '6px', height: '44px', borderRadius: '4px', backgroundColor: style.badge, flexShrink: 0 }} />

          {/* Name + room */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ margin: 0, fontWeight: 700, color: 'var(--midnight-green)', fontSize: '0.95rem' }}>{score.resident_name}</p>
            <p style={{ margin: '0.2rem 0 0', color: 'var(--text-light)', fontSize: '0.82rem' }}>Room {score.room_number}</p>
          </div>

          {/* Score bar */}
          <div style={{ flex: 1, minWidth: '120px' }}>
            <div style={{ height: '6px', backgroundColor: '#EEF2F5', borderRadius: '4px', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${Math.round(score.score * 100)}%`, backgroundColor: style.badge, borderRadius: '4px', transition: 'width 0.6s ease' }} />
            </div>
            <p style={{ margin: '0.3rem 0 0', fontSize: '0.78rem', color: 'var(--text-light)' }}>{Math.round(score.score * 100)}% risk</p>
          </div>

          {/* Badge */}
          <span style={{ padding: '5px 12px', borderRadius: '999px', backgroundColor: style.bg, color: style.text, fontSize: '0.78rem', fontWeight: 700, flexShrink: 0 }}>
            {style.label}
          </span>

          {/* Actions */}
          <div style={{ display: 'flex', gap: '0.5rem', flexShrink: 0 }}>
            <button
              onClick={() => setShowLogModal(true)}
              style={{ border: 'none', borderRadius: '10px', padding: '8px 14px', backgroundColor: 'var(--alice-blue)', color: 'var(--midnight-green)', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem' }}
            >
              <Plus size={14} /> Log
            </button>
            <button
              onClick={handleExpand}
              style={{ border: 'none', borderRadius: '10px', padding: '8px 10px', backgroundColor: 'var(--alice-blue)', color: 'var(--midnight-green)', cursor: 'pointer' }}
            >
              {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
          </div>
        </div>

        {/* Contributing factors */}
        {score.contributing_factors?.length > 0 && (
          <div style={{ padding: '0 1.25rem 0.75rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {score.contributing_factors.map(f => (
              <span key={f} style={{ padding: '3px 10px', borderRadius: '999px', backgroundColor: '#FFF7ED', color: '#9A3412', fontSize: '0.75rem', fontWeight: 600 }}>
                {f.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        )}

        {/* Expanded: recent logs */}
        {expanded && (
          <div style={{ borderTop: '1px solid #EEF2F5', padding: '1rem 1.25rem', backgroundColor: '#FAFCFE' }}>
            <p style={{ margin: '0 0 0.75rem', fontWeight: 700, color: 'var(--midnight-green)', fontSize: '0.85rem' }}>Last 7 days — Medication Logs</p>
            {loadingHistory ? (
              <p style={{ color: 'var(--text-light)', fontSize: '0.85rem' }}>Loading...</p>
            ) : history.length > 0 ? (
              <div style={{ display: 'grid', gap: '0.5rem' }}>
                {history.slice(0, 5).map(log => {
                  const statusColors = {
                    taken:   { bg: '#ECFDF5', text: '#065F46', icon: '✅' },
                    missed:  { bg: '#FEF2F2', text: '#B91C1C', icon: '❌' },
                    late:    { bg: '#FFF7ED', text: '#9A3412', icon: '⏰' },
                    refused: { bg: '#FDF4FF', text: '#6B21A8', icon: '🚫' },
                  };
                  const sc = statusColors[log.status] || statusColors.taken;
                  return (
                    <div key={log.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.6rem 0.9rem', backgroundColor: sc.bg, borderRadius: '10px', gap: '1rem' }}>
                      <span style={{ fontWeight: 600, color: sc.text, fontSize: '0.85rem' }}>{sc.icon} {log.medication_name}</span>
                      <span style={{ color: 'var(--text-light)', fontSize: '0.78rem', whiteSpace: 'nowrap' }}>{new Date(log.scheduled_at).toLocaleDateString()}</span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p style={{ color: 'var(--text-light)', fontSize: '0.85rem', margin: 0 }}>No logs yet for this resident.</p>
            )}
          </div>
        )}
      </div>
    </>
  );
}

// ─── Main Panel ────────────────────────────────────────────────────────────────
export default function MedicationPanel({ token, onLogout }) {
  const [scores, setScores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('all'); // all | high | medium | low

  const loadScores = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/adherence/risk/today/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setScores(res.data);
    } catch (err) {
      if (err.response?.status === 401) onLogout();
      else setError('Could not load medication risk scores.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadScores(); }, [token]);

  const filtered = filter === 'all' ? scores : scores.filter(s => s.risk_level === filter);
  const highCount   = scores.filter(s => s.risk_level === 'high').length;
  const mediumCount = scores.filter(s => s.risk_level === 'medium').length;
  const lowCount    = scores.filter(s => s.risk_level === 'low').length;

  if (loading) return <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--midnight-green)' }}><h2>Loading medication risk scores...</h2></div>;

  return (
    <div style={{ display: 'grid', gap: '1.5rem' }}>

      {/* Header stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
        <div style={{ ...sectionCardStyle, borderTop: '4px solid #EF4444' }}>
          <p style={{ margin: 0, color: 'var(--text-light)', fontWeight: 600 }}>High Risk</p>
          <h2 style={{ margin: '0.4rem 0 0', color: '#B91C1C', fontSize: '2rem' }}>{highCount}</h2>
          <p style={{ margin: '0.3rem 0 0', color: 'var(--text-light)', fontSize: '0.85rem' }}>Residents likely to refuse medication</p>
        </div>
        <div style={{ ...sectionCardStyle, borderTop: '4px solid #F59E0B' }}>
          <p style={{ margin: 0, color: 'var(--text-light)', fontWeight: 600 }}>Medium Risk</p>
          <h2 style={{ margin: '0.4rem 0 0', color: '#B45309', fontSize: '2rem' }}>{mediumCount}</h2>
          <p style={{ margin: '0.3rem 0 0', color: 'var(--text-light)', fontSize: '0.85rem' }}>Show attention during administration</p>
        </div>
        <div style={{ ...sectionCardStyle, borderTop: '4px solid #10B981' }}>
          <p style={{ margin: 0, color: 'var(--text-light)', fontWeight: 600 }}>Low Risk</p>
          <h2 style={{ margin: '0.4rem 0 0', color: '#065F46', fontSize: '2rem' }}>{lowCount}</h2>
          <p style={{ margin: '0.3rem 0 0', color: 'var(--text-light)', fontSize: '0.85rem' }}>On track with medication</p>
        </div>
        
      </div>

      {/* Risk list */}
      <section style={sectionCardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h3 style={{ margin: 0, color: 'var(--midnight-green)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Pill size={18} color="var(--moonstone)" /> Medication Refusal Risk — Today
            </h3>
            <p style={{ margin: '0.35rem 0 0', color: 'var(--text-light)' }}>
              {new Date().toLocaleDateString('en-GB', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
            </p>
          </div>

          {/* Filter buttons */}
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {['all', 'high', 'medium', 'low'].map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                style={{
                  border: 'none', borderRadius: '999px', padding: '8px 16px',
                  backgroundColor: filter === f ? 'var(--midnight-green)' : 'var(--alice-blue)',
                  color: filter === f ? 'white' : 'var(--midnight-green)',
                  fontWeight: 700, cursor: 'pointer', fontSize: '0.85rem', textTransform: 'capitalize',
                }}
              >
                {f === 'all' ? `All (${scores.length})` : f === 'high' ? `🔴 High (${highCount})` : f === 'medium' ? `🟡 Medium (${mediumCount})` : `🟢 Low (${lowCount})`}
              </button>
            ))}
            <button
              onClick={loadScores}
              style={{ border: '1px solid #D7E3EA', borderRadius: '999px', padding: '8px 16px', backgroundColor: 'white', color: 'var(--midnight-green)', fontWeight: 700, cursor: 'pointer', fontSize: '0.85rem' }}
            >
              Refresh
            </button>
          </div>
        </div>

        {error && (
          <div style={{ backgroundColor: '#FEF2F2', color: '#B91C1C', padding: '1rem', borderRadius: '12px', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertCircle size={18} /> {error}
          </div>
        )}

        {filtered.length > 0 ? (
          <div style={{ display: 'grid', gap: '0.75rem' }}>
            {filtered.map(score => (
              <ResidentRiskRow
                key={score.id}
                score={score}
                token={token}
                onLogSaved={loadScores}
              />
            ))}
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-light)' }}>
            <CheckCircle2 size={40} color="#10B981" style={{ marginBottom: '0.75rem', opacity: 0.6 }} />
            <p style={{ margin: 0, fontWeight: 700 }}>No residents in this category today</p>
          </div>
        )}
      </section>

      
    </div>
  );
}
