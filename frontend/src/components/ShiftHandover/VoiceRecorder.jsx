import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';

const VoiceRecorder = ({ onSuccess }) => {
  const [recording, setRecording] = useState(false);
  const [transcription, setTranscription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [caregiverName, setCaregiverName] = useState('');
  const [selectedShiftId, setSelectedShiftId] = useState('');
  const [selectedPatient, setSelectedPatient] = useState('');
  const [shifts, setShifts] = useState([]);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  useEffect(() => {
    fetchShifts();
  }, []);

  const fetchShifts = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/voice/shifts/');
      if (response.data.success && response.data.shifts.length > 0) {
        setShifts(response.data.shifts);
        setSelectedShiftId(response.data.shifts[0].id);
      }
    } catch (error) {
      console.error('Error fetching shifts:', error);
    }
  };

  const startRecording = async () => {
    setError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (event) => {
        audioChunksRef.current.push(event.data);
      };

      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        await uploadAudio(audioBlob);
      };

      mediaRecorderRef.current.start();
      setRecording(true);
    } catch (err) {
      setError('Microphone access denied. Please allow microphone access.');
      console.error(err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      setRecording(false);
      mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
    }
  };

  const uploadAudio = async (audioBlob) => {
    setLoading(true);
    setError('');
    const formData = new FormData();
    formData.append('audio_file', audioBlob, 'recording.wav');
    formData.append('caregiver_name', caregiverName || 'Caregiver');
    formData.append('shift_id', selectedShiftId);
    formData.append('patient_name', selectedPatient);

    try {
      const response = await axios.post('http://localhost:8000/api/voice/upload/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000
      });
      
      if (response.data.success) {
        setTranscription(response.data.transcription);
        setCaregiverName('');
        setSelectedPatient('');
        if (onSuccess) onSuccess();
      } else {
        setError(response.data.error || 'Transcription failed');
      }
    } catch (error) {
      console.error('Upload error:', error);
      setError('Upload failed. Check if Django is running.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="voice-recorder-card">
      <div className="voice-recorder-header">
        <h2 className="voice-recorder-title">Shift Handover - Voice Recording</h2>
        <p className="voice-recorder-subtitle">
          Record your handover notes. Whisper AI will transcribe your voice.
        </p>
      </div>

      <div className="voice-recorder-form">
        <div className="form-group">
          <label className="form-label">Caregiver Name <span className="required">*</span></label>
          <input
            type="text"
            value={caregiverName}
            onChange={(e) => setCaregiverName(e.target.value)}
            placeholder="Enter your name"
            className="form-input"
            required
          />
        </div>
        
        <div className="form-group">
          <label className="form-label">Shift</label>
          <select
            value={selectedShiftId}
            onChange={(e) => setSelectedShiftId(e.target.value)}
            className="form-select"
          >
            {shifts.map(shift => (
              <option key={shift.id} value={shift.id}>
                {shift.display_name}
              </option>
            ))}
          </select>
        </div>
        
        <div className="form-group">
          <label className="form-label">Patient <span className="optional">(optional)</span></label>
          <input
            type="text"
            value={selectedPatient}
            onChange={(e) => setSelectedPatient(e.target.value)}
            placeholder="Patient name"
            className="form-input"
          />
        </div>
      </div>
      
      {error && (
        <div className="alert alert-error">
          {error}
        </div>
      )}
      
      <button 
        onClick={recording ? stopRecording : startRecording}
        disabled={!caregiverName}
        className={`record-button ${recording ? 'recording' : ''} ${!caregiverName ? 'disabled' : ''}`}
      >
        <span className="button-icon">{recording ? '■' : '●'}</span>
        {recording ? 'Stop Recording' : 'Start Recording'}
      </button>

      {loading && (
        <div className="loading-indicator">
          <span className="loading-spinner"></span>
          Transcribing with Whisper...
        </div>
      )}

      {transcription && (
        <div className="transcription-result">
          <h3 className="transcription-title">Transcription</h3>
          <p className="transcription-text">{transcription}</p>
        </div>
      )}

      <style>{`
        .voice-recorder-card {
          background-color: white;
          border-radius: 12px;
          padding: 24px;
          margin-bottom: 24px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
          border: 1px solid #eef2f6;
        }

        .voice-recorder-header {
          margin-bottom: 24px;
          padding-bottom: 16px;
          border-bottom: 1px solid #eef2f6;
        }

        .voice-recorder-title {
          font-size: 18px;
          font-weight: 600;
          color: #1a3a3a;
          margin: 0 0 6px 0;
          letter-spacing: -0.01em;
        }

        .voice-recorder-subtitle {
          font-size: 13px;
          color: #6b7a8a;
          margin: 0;
          line-height: 1.5;
        }

        .voice-recorder-form {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: 20px;
          margin-bottom: 24px;
        }

        .form-group {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .form-label {
          font-size: 12px;
          font-weight: 600;
          color: #2c3e50;
          letter-spacing: 0.3px;
        }

        .required {
          color: #e74c3c;
          margin-left: 2px;
        }

        .optional {
          font-weight: 400;
          color: #8a9aa8;
          font-size: 11px;
        }

        .form-input,
        .form-select {
          width: 100%;
          padding: 10px 14px;
          border-radius: 8px;
          border: 1px solid #dce5ec;
          font-size: 14px;
          color: #2c3e50;
          background-color: #ffffff;
          transition: all 0.2s ease;
          box-sizing: border-box;
        }

        .form-input:focus,
        .form-select:focus {
          outline: none;
          border-color: #5b8c8c;
          box-shadow: 0 0 0 3px rgba(91, 140, 140, 0.1);
        }

        .form-input::placeholder {
          color: #b8c5d0;
        }

        .alert {
          padding: 12px 16px;
          border-radius: 8px;
          margin-bottom: 20px;
          font-size: 13px;
          font-weight: 500;
        }

        .alert-error {
          background-color: #fef2f2;
          color: #c0392b;
          border-left: 3px solid #e74c3c;
        }

        .record-button {
          display: inline-flex;
          align-items: center;
          gap: 10px;
          padding: 12px 28px;
          font-size: 14px;
          font-weight: 600;
          background-color: #2c6e6e;
          color: white;
          border: none;
          border-radius: 40px;
          cursor: pointer;
          transition: all 0.2s ease;
          letter-spacing: 0.3px;
        }

        .record-button:hover:not(:disabled) {
          background-color: #1e5a5a;
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(44, 110, 110, 0.2);
        }

        .record-button.recording {
          background-color: #c0392b;
        }

        .record-button.recording:hover:not(:disabled) {
          background-color: #a93226;
        }

        .record-button.disabled {
          background-color: #b8c5d0;
          cursor: not-allowed;
          opacity: 0.7;
        }

        .button-icon {
          font-size: 14px;
          font-weight: normal;
        }

        .loading-indicator {
          margin-top: 20px;
          padding: 12px 16px;
          background-color: #fef9e6;
          color: #8a6e2b;
          border-radius: 8px;
          display: flex;
          align-items: center;
          gap: 12px;
          font-size: 13px;
          border-left: 3px solid #e6b12e;
        }

        .loading-spinner {
          width: 16px;
          height: 16px;
          border: 2px solid #e6b12e;
          border-top-color: transparent;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .transcription-result {
          margin-top: 24px;
          padding: 18px 20px;
          background-color: #f0f6f4;
          border-radius: 10px;
          border-left: 3px solid #2c6e6e;
        }

        .transcription-title {
          margin: 0 0 10px 0;
          font-size: 13px;
          font-weight: 600;
          color: #2c6e6e;
          letter-spacing: 0.5px;
        }

        .transcription-text {
          margin: 0;
          font-size: 14px;
          line-height: 1.6;
          color: #2c3e50;
        }
      `}</style>
    </div>
  );
};

export default VoiceRecorder;