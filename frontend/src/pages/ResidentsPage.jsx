import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { Users, Upload, Trash2, CheckCircle, XCircle, Camera, RefreshCw } from 'lucide-react';

const API_HOST = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';
const API_BASE = `http://${API_HOST}:8000/api`;

const Card = ({ children, style }) => (
  <div style={{
    backgroundColor: 'white', borderRadius: 'var(--border-radius)',
    boxShadow: 'var(--box-shadow)', padding: '1.5rem', ...style,
  }}>{children}</div>
);

const RiskBadge = ({ level }) => {
  const MAP = {
    LOW:    { bg: '#D1FAE5', color: '#065F46', label: 'Faible' },
    MEDIUM: { bg: '#FEF3C7', color: '#B45309', label: 'Moyen' },
    HIGH:   { bg: '#FEE2E2', color: '#B91C1C', label: 'Élevé' },
  };
  const s = MAP[level] || MAP.LOW;
  return (
    <span style={{
      padding: '2px 10px', borderRadius: 99, fontSize: 11, fontWeight: 700,
      background: s.bg, color: s.color,
    }}>{s.label}</span>
  );
};

export default function ResidentsPage({ token, onLogout }) {
  const [residents, setResidents] = useState([]);
  const [faceStatus, setFaceStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploadingId, setUploadingId] = useState(null);
  const [uploadError, setUploadError] = useState({});
  const [uploadSuccess, setUploadSuccess] = useState({});
  const [previewMap, setPreviewMap] = useState({});
  const fileInputRefs = useRef({});

  const authHeader = { Authorization: `Bearer ${token}` };

  const fetchData = useCallback(async () => {
    try {
      const [resRes, faceRes] = await Promise.all([
        axios.get(`${API_BASE}/residents/`, { headers: authHeader }),
        axios.get(`${API_BASE}/face/status/`, { headers: authHeader }),
      ]);
      setResidents(Array.isArray(resRes.data) ? resRes.data : []);
      setFaceStatus(faceRes.data);
    } catch (e) {
      if (e.response?.status === 401) onLogout();
    } finally {
      setLoading(false);
    }
  }, [token]); // eslint-disable-line

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleFileSelect = (residentId, file) => {
    if (!file) return;
    // Prévisualisation locale
    const url = URL.createObjectURL(file);
    setPreviewMap(prev => ({ ...prev, [residentId]: url }));
    setUploadError(prev => ({ ...prev, [residentId]: null }));
    setUploadSuccess(prev => ({ ...prev, [residentId]: null }));
  };

  const handleUpload = async (residentId) => {
    const input = fileInputRefs.current[residentId];
    if (!input?.files[0]) return;

    const file = input.files[0];
    setUploadingId(residentId);
    setUploadError(prev => ({ ...prev, [residentId]: null }));
    setUploadSuccess(prev => ({ ...prev, [residentId]: null }));

    const form = new FormData();
    form.append('photo', file);

    try {
      const res = await axios.post(
        `${API_BASE}/residents/${residentId}/photo/`,
        form,
        { headers: { ...authHeader, 'Content-Type': 'multipart/form-data' } }
      );
      setUploadSuccess(prev => ({ ...prev, [residentId]: res.data.message || 'Photo enregistrée ✓' }));
      // Met à jour l'URL photo dans la liste locale
      setResidents(prev => prev.map(r =>
        r.id === residentId
          ? { ...r, photo_url: res.data.photo_url, has_face_encoding: true }
          : r
      ));
      fetchData(); // rafraîchit le statut global
    } catch (e) {
      const msg = e.response?.data?.error || 'Erreur lors du téléversement';
      setUploadError(prev => ({ ...prev, [residentId]: msg }));
    } finally {
      setUploadingId(null);
    }
  };

  const handleDeletePhoto = async (residentId) => {
    if (!window.confirm('Supprimer la photo et l\'encodage facial de ce résident ?')) return;
    try {
      await axios.delete(`${API_BASE}/residents/${residentId}/photo/`, { headers: authHeader });
      setResidents(prev => prev.map(r =>
        r.id === residentId ? { ...r, photo_url: null, has_face_encoding: false } : r
      ));
      setPreviewMap(prev => { const n = { ...prev }; delete n[residentId]; return n; });
      fetchData();
    } catch (e) {
      if (e.response?.status === 401) onLogout();
    }
  };

  if (loading) {
    return (
      <div style={{ flex: 1, padding: '2.5rem', background: 'var(--alice-blue)', minHeight: '100vh' }}>
        <Card><p style={{ margin: 0, color: 'var(--midnight-green)', fontWeight: 700 }}>Chargement des résidents…</p></Card>
      </div>
    );
  }

  const encodedCount = faceStatus?.with_encoding ?? residents.filter(r => r.has_face_encoding).length;
  const totalCount   = faceStatus?.total_residents ?? residents.length;

  return (
    <div style={{ flex: 1, padding: '2.5rem', background: 'var(--alice-blue)', overflowY: 'auto', minHeight: '100vh' }}>

      {/* En-tête */}
      <div style={{ marginBottom: '2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ color: 'var(--midnight-green)', margin: 0, fontSize: '1.8rem', display: 'flex', alignItems: 'center', gap: 10 }}>
            <Users size={26} /> Base de données des résidents
          </h1>
          <p style={{ color: 'var(--text-light)', margin: '4px 0 0', fontSize: 14 }}>
            Gérez les photos des résidents utilisées pour la reconnaissance faciale automatique.
          </p>
        </div>
        <button
          onClick={fetchData}
          style={{
            display: 'flex', alignItems: 'center', gap: 6, padding: '9px 16px',
            borderRadius: 'var(--border-radius-sm)', border: '1px solid #D7E3EA',
            background: 'white', color: 'var(--midnight-green)', fontWeight: 700,
            fontSize: 13, cursor: 'pointer',
          }}
        >
          <RefreshCw size={14} /> Actualiser
        </button>
      </div>

      {/* Résumé reconnaissance faciale */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1.5rem', marginBottom: '2rem' }}>
        {[
          { label: 'Total résidents', value: totalCount, color: 'var(--midnight-green)', icon: <Users size={20} /> },
          {
            label: 'Avec encodage facial', value: encodedCount,
            color: '#10B981', icon: <CheckCircle size={20} />,
          },
          {
            label: 'Sans encodage facial', value: totalCount - encodedCount,
            color: '#F59E0B', icon: <XCircle size={20} />,
          },
        ].map(k => (
          <Card key={k.label}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: 12, color: 'var(--text-light)', fontWeight: 600 }}>{k.label}</span>
              <span style={{ color: k.color }}>{k.icon}</span>
            </div>
            <div style={{ fontSize: '2.2rem', fontWeight: 800, color: k.color }}>{k.value}</div>
          </Card>
        ))}
      </div>

      {/* Barre de progression encodage */}
      <Card style={{ marginBottom: '2rem', padding: '1rem 1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 8 }}>
          <span style={{ fontWeight: 700, color: 'var(--midnight-green)' }}>
            <Camera size={14} style={{ verticalAlign: 'middle', marginRight: 5 }} />
            Couverture de la reconnaissance faciale
          </span>
          <strong style={{ color: 'var(--midnight-green)' }}>
            {totalCount > 0 ? Math.round(encodedCount / totalCount * 100) : 0}%
          </strong>
        </div>
        <div style={{ height: 10, background: '#E9F1F6', borderRadius: 99, overflow: 'hidden' }}>
          <div style={{
            height: '100%',
            width: `${totalCount > 0 ? Math.round(encodedCount / totalCount * 100) : 0}%`,
            background: 'linear-gradient(90deg, var(--moonstone), var(--midnight-green))',
            borderRadius: 99, transition: 'width 0.5s',
          }} />
        </div>
        <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--text-light)' }}>
          {encodedCount} / {totalCount} résidents ont une photo encodée. Ajoutez des photos pour améliorer la reconnaissance en temps réel.
        </p>
      </Card>

      {/* Grille des résidents */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1.5rem' }}>
        {residents.map(resident => {
          const preview    = previewMap[resident.id];
          const photoSrc   = preview || resident.photo_url;
          const isUploading = uploadingId === resident.id;
          const error      = uploadError[resident.id];
          const success    = uploadSuccess[resident.id];

          return (
            <Card key={resident.id} style={{ padding: '1.25rem' }}>
              {/* En-tête résident */}
              <div style={{ display: 'flex', gap: 14, marginBottom: '1rem', alignItems: 'flex-start' }}>
                {/* Avatar / Photo */}
                <div style={{
                  width: 72, height: 72, borderRadius: '50%', flexShrink: 0,
                  background: photoSrc ? 'transparent' : '#E9F1F6',
                  border: '3px solid',
                  borderColor: resident.has_face_encoding ? '#10B981' : '#CBD5E1',
                  overflow: 'hidden', position: 'relative',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  {photoSrc ? (
                    <img
                      src={photoSrc}
                      alt={resident.name}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    />
                  ) : (
                    <Users size={30} color="#94A3B8" />
                  )}
                  {/* Badge encodage */}
                  <div style={{
                    position: 'absolute', bottom: -2, right: -2,
                    width: 20, height: 20, borderRadius: '50%',
                    background: resident.has_face_encoding ? '#10B981' : '#CBD5E1',
                    border: '2px solid white',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    {resident.has_face_encoding
                      ? <CheckCircle size={11} color="white" />
                      : <XCircle size={11} color="white" />
                    }
                  </div>
                </div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 800, color: 'var(--midnight-green)', fontSize: 15, marginBottom: 2 }}>
                    {resident.name}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-light)', marginBottom: 5 }}>
                    Chambre {resident.room_number} · {resident.age} ans
                  </div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <RiskBadge level={resident.risk_level} />
                    <span style={{
                      padding: '2px 9px', borderRadius: 99, fontSize: 11, fontWeight: 700,
                      background: resident.has_face_encoding ? '#D1FAE5' : '#F1F5F9',
                      color: resident.has_face_encoding ? '#065F46' : '#64748B',
                    }}>
                      {resident.has_face_encoding ? '✓ Encodé' : '○ Non encodé'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Zone upload photo */}
              <div style={{
                border: '2px dashed',
                borderColor: preview ? 'var(--moonstone)' : '#E2E8F0',
                borderRadius: 12, padding: '0.85rem 1rem',
                background: preview ? '#F0FDFC' : 'var(--alice-blue)',
                marginBottom: 10,
                transition: 'all 0.2s',
              }}>
                <label
                  htmlFor={`photo-${resident.id}`}
                  style={{ cursor: 'pointer', display: 'block' }}
                  onDragOver={e => e.preventDefault()}
                  onDrop={e => {
                    e.preventDefault();
                    const f = e.dataTransfer.files[0];
                    if (f && f.type.startsWith('image/')) {
                      handleFileSelect(resident.id, f);
                      // Injecter dans l'input réel
                      const dt = new DataTransfer();
                      dt.items.add(f);
                      if (fileInputRefs.current[resident.id]) {
                        fileInputRefs.current[resident.id].files = dt.files;
                      }
                    }
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Upload size={16} color="var(--moonstone)" style={{ flexShrink: 0 }} />
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--midnight-green)' }}>
                        {preview ? 'Nouvelle photo sélectionnée' : resident.photo_url ? 'Remplacer la photo' : 'Ajouter une photo'}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-light)' }}>
                        {preview ? 'Cliquez pour en choisir une autre' : 'Glissez ou cliquez · JPG, PNG, WEBP'}
                      </div>
                    </div>
                  </div>
                </label>
                <input
                  id={`photo-${resident.id}`}
                  type="file"
                  accept="image/*"
                  style={{ display: 'none' }}
                  ref={el => { fileInputRefs.current[resident.id] = el; }}
                  onChange={e => handleFileSelect(resident.id, e.target.files[0])}
                />
              </div>

              {/* Messages */}
              {error && (
                <div style={{
                  padding: '8px 12px', borderRadius: 10, background: '#FEF2F2',
                  border: '1px solid #FECACA', fontSize: 12, color: '#B91C1C',
                  marginBottom: 10, fontWeight: 600,
                }}>
                  ⚠ {error}
                </div>
              )}
              {success && (
                <div style={{
                  padding: '8px 12px', borderRadius: 10, background: '#ECFDF5',
                  border: '1px solid #6EE7B7', fontSize: 12, color: '#065F46',
                  marginBottom: 10, fontWeight: 600,
                }}>
                  ✓ {success}
                </div>
              )}

              {/* Boutons */}
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  onClick={() => handleUpload(resident.id)}
                  disabled={isUploading || !previewMap[resident.id]}
                  style={{
                    flex: 1, padding: '9px 12px', borderRadius: 10, border: 'none',
                    fontWeight: 700, fontSize: 12, cursor: (isUploading || !previewMap[resident.id]) ? 'not-allowed' : 'pointer',
                    background: (isUploading || !previewMap[resident.id]) ? '#E2E8F0' : 'var(--midnight-green)',
                    color: (isUploading || !previewMap[resident.id]) ? 'var(--text-light)' : 'white',
                    transition: 'all 0.2s', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                  }}
                >
                  {isUploading
                    ? <><span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⟳</span> Encodage…</>
                    : <><Upload size={13} /> Enregistrer</>
                  }
                </button>

                {resident.photo_url && (
                  <button
                    onClick={() => handleDeletePhoto(resident.id)}
                    style={{
                      padding: '9px 12px', borderRadius: 10, border: '1px solid #FECACA',
                      background: 'white', color: '#B91C1C', cursor: 'pointer',
                      fontWeight: 700, fontSize: 12, display: 'flex', alignItems: 'center', gap: 5,
                    }}
                  >
                    <Trash2 size={13} /> Supprimer
                  </button>
                )}
              </div>
            </Card>
          );
        })}
      </div>

      {residents.length === 0 && (
        <Card style={{ textAlign: 'center', padding: '3rem' }}>
          <Users size={48} style={{ color: '#CBD5E1', marginBottom: 12 }} />
          <p style={{ color: 'var(--text-light)', fontWeight: 600, margin: 0 }}>
            Aucun résident trouvé. Ajoutez des résidents depuis le panneau d'administration.
          </p>
        </Card>
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
