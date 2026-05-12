import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Modal from './Modal';

const ReportsDashboard = ({ refreshTrigger, role }) => {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [reportToDelete, setReportToDelete] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editText, setEditText] = useState('');
  const [saving, setSaving] = useState(false);

  const fetchReports = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/voice/reports/');
      if (response.data.success) {
        setReports(response.data.reports);
      }
    } catch (error) {
      console.error('Error fetching reports:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [refreshTrigger]);

  const handleDeleteClick = (id) => {
    setReportToDelete(id);
    setModalOpen(true);
  };

  const confirmDelete = async () => {
    if (reportToDelete) {
      try {
        await axios.delete(`http://localhost:8000/api/voice/reports/${reportToDelete}/delete/`);
        fetchReports();
      } catch (error) {
        console.error('Delete error:', error);
        alert('Error deleting report');
      } finally {
        setModalOpen(false);
        setReportToDelete(null);
      }
    }
  };

  const cancelDelete = () => {
    setModalOpen(false);
    setReportToDelete(null);
  };

  const startEdit = (report) => {
    setEditingId(report.id);
    setEditText(report.transcription);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditText('');
  };

  const saveEdit = async (id) => {
    setSaving(true);
    try {
      await axios.put(`http://localhost:8000/api/voice/reports/${id}/update/`, {
        transcription: editText
      });
      setEditingId(null);
      fetchReports();
    } catch (error) {
      console.error('Save error:', error);
      alert('Error saving correction');
    } finally {
      setSaving(false);
    }
  };

  const getShiftColor = (shiftName) => {
    if (shiftName.includes('Morning') || shiftName.includes('MORNING')) {
      return { bg: '#eaf7ea', text: '#2d6a2d', border: '#4a8c4a' };
    } else if (shiftName.includes('Afternoon') || shiftName.includes('AFTERNOON')) {
      return { bg: '#fff4e6', text: '#8a6e2b', border: '#d4a53a' };
    } else {
      return { bg: '#e6f3f5', text: '#2c6e6e', border: '#4a9a9a' };
    }
  };
  // Ajoute cette fonction avant le return (vers ligne ~70)
  const formatDate = (dateStr) => {
    const date = new Date(dateStr);
    // Ajoute 1 heure pour corriger le décalage (Tunis UTC+1)
    date.setHours(date.getHours() + 1);
    return date.toLocaleString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };
  if (loading) return <div className="reports-loading">Loading reports...</div>;

  return (
    <div className="reports-dashboard">
      <div className="reports-header">
        <h2 className="reports-title">Shift Handover Reports</h2>
      </div>
      
      {reports.length === 0 && (
        <p className="reports-empty">No reports yet. Record your first handover.</p>
      )}
      
      <div className="reports-list">
        {reports.map((report) => {
          const colors = getShiftColor(report.shift);
          const isEditing = editingId === report.id;
          
          return (
            <div key={report.id} className="report-card" style={{ borderLeftColor: colors.border }}>
              <button
                onClick={() => handleDeleteClick(report.id)}
                className="delete-button"
                aria-label="Delete report"
              >
                ×
              </button>
              
              <div className="report-header">
                <strong className="caregiver-name">{report.caregiver_name}</strong>
                <span className="shift-badge" style={{ backgroundColor: colors.bg, color: colors.text }}>
                  {report.shift}
                </span>
              </div>
              
              {report.patient_name && report.patient_name.trim() !== '' && report.patient_name !== 'Patient' && (
                <div className="patient-info">
                  <span className="patient-label">Patient</span>
                  <span className="patient-name">{report.patient_name}</span>
                </div>
              )}
              
              {isEditing ? (
                <div className="edit-section">
                  <textarea
                    value={editText}
                    onChange={(e) => setEditText(e.target.value)}
                    className="edit-textarea"
                    rows="3"
                    disabled={saving}
                  />
                  <div className="edit-actions">
                    <button
                      onClick={() => saveEdit(report.id)}
                      className="save-button"
                      disabled={saving}
                    >
                      {saving ? 'Saving...' : 'Save'}
                    </button>
                    <button
                      onClick={cancelEdit}
                      className="cancel-button"
                      disabled={saving}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="transcription-content">
                  <p className="transcription-text">{report.transcription}</p>
                  {role === 'ADMIN' && (
                    <button
                      onClick={() => startEdit(report)}
                      className="edit-transcription-button"
                      title="Edit transcription"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M17 3l4 4-7 7H10v-4l7-7z" />
                        <path d="M4 20h16" />
                      </svg>
                      Edit
                    </button>
                  )}
                </div>
              )}
              
              <div className="report-footer">
                <span className="report-date">{formatDate(report.created_at)}</span>
              </div>
            </div>
          );
        })}
      </div>
      
      <Modal
        isOpen={modalOpen}
        onClose={cancelDelete}
        onConfirm={confirmDelete}
        title="Confirm"
        message="Delete this report?"
      />

      <style>{`
        .reports-dashboard {
          padding: 20px;
        }

        .reports-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
          padding-bottom: 12px;
          border-bottom: 1px solid #eef2f6;
        }

        .reports-title {
          margin: 0;
          font-size: 18px;
          font-weight: 600;
          color: #1a3a3a;
          letter-spacing: -0.3px;
        }

        .reports-empty {
          color: #8a9aa8;
          text-align: center;
          padding: 40px 20px;
          background-color: #fafcfd;
          border-radius: 10px;
          font-size: 13px;
        }

        .reports-loading {
          padding: 40px;
          text-align: center;
          color: #6b7a8a;
          font-size: 13px;
        }

        .reports-list {
          display: flex;
          flex-direction: column;
          gap: 14px;
        }

        .report-card {
          border-left: 4px solid;
          border-radius: 8px;
          padding: 16px 18px;
          background-color: #ffffff;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
          transition: all 0.2s ease;
          position: relative;
        }

        .report-card:hover {
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        }

        .delete-button {
          position: absolute;
          top: 14px;
          right: 14px;
          background: transparent;
          color: #b8c5d0;
          border: none;
          border-radius: 50%;
          width: 28px;
          height: 28px;
          cursor: pointer;
          font-size: 18px;
          font-weight: 400;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.2s ease;
          font-family: monospace;
        }

        .delete-button:hover {
          background-color: #fef2f2;
          color: #c0392b;
          transform: scale(1.05);
        }

        .report-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex-wrap: wrap;
          gap: 10px;
          margin-bottom: 12px;
          padding-right: 32px;
        }

        .caregiver-name {
          font-size: 14px;
          font-weight: 600;
          color: #2c3e50;
        }

        .shift-badge {
          padding: 4px 12px;
          border-radius: 20px;
          font-size: 11px;
          font-weight: 600;
          letter-spacing: 0.3px;
        }

        .patient-info {
          display: flex;
          align-items: baseline;
          gap: 8px;
          margin-bottom: 12px;
          font-size: 12px;
          flex-wrap: wrap;
        }

        .patient-label {
          color: #8a9aa8;
          font-weight: 500;
          text-transform: uppercase;
          font-size: 10px;
          letter-spacing: 0.5px;
        }

        .patient-name {
          color: #5b8c8c;
          font-weight: 500;
        }

        .transcription-content {
          background-color: #fafcfd;
          padding: 12px 14px;
          border-radius: 8px;
          margin: 12px 0;
          border: 1px solid #eef2f6;
          position: relative;
        }

        .transcription-text {
          margin: 0;
          font-size: 13px;
          line-height: 1.55;
          color: #2c3e50;
          padding-right: 50px;
        }

        .edit-transcription-button {
          position: absolute;
          bottom: 10px;
          right: 10px;
          background: transparent;
          border: none;
          color: #8a9aa8;
          cursor: pointer;
          font-size: 11px;
          display: flex;
          align-items: center;
          gap: 4px;
          padding: 4px 8px;
          border-radius: 4px;
          transition: all 0.2s ease;
        }

        .edit-transcription-button:hover {
          background-color: #eef2f6;
          color: #5b8c8c;
        }

        .edit-section {
          margin: 12px 0;
        }

        .edit-textarea {
          width: 100%;
          padding: 12px;
          border-radius: 8px;
          border: 1px solid #dce5ec;
          font-size: 13px;
          line-height: 1.55;
          font-family: inherit;
          color: #2c3e50;
          background-color: #ffffff;
          resize: vertical;
          box-sizing: border-box;
        }

        .edit-textarea:focus {
          outline: none;
          border-color: #5b8c8c;
          box-shadow: 0 0 0 3px rgba(91, 140, 140, 0.1);
        }

        .edit-actions {
          display: flex;
          gap: 10px;
          margin-top: 10px;
        }

        .save-button {
          padding: 6px 16px;
          background-color: #2c6e6e;
          color: white;
          border: none;
          border-radius: 6px;
          font-size: 12px;
          font-weight: 500;
          cursor: pointer;
          transition: background-color 0.2s ease;
        }

        .save-button:hover {
          background-color: #1e5a5a;
        }

        .save-button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .cancel-button {
          padding: 6px 16px;
          background-color: #eef2f6;
          color: #2c3e50;
          border: none;
          border-radius: 6px;
          font-size: 12px;
          font-weight: 500;
          cursor: pointer;
          transition: background-color 0.2s ease;
        }

        .cancel-button:hover {
          background-color: #e2e8ed;
        }

        .cancel-button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .report-footer {
          display: flex;
          justify-content: flex-end;
          margin-top: 10px;
        }

        .report-date {
          font-size: 10px;
          color: #b8c5d0;
          font-feature-settings: 'tnum';
          letter-spacing: 0.2px;
        }
      `}</style>
    </div>
  );
};

export default ReportsDashboard;