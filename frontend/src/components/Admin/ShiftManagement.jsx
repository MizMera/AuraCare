import React, { useState, useEffect } from 'react';
import axios from 'axios';

const ShiftManagement = () => {
  const [shifts, setShifts] = useState([]);
  const [form, setForm] = useState({ name: '', start_time: '08:00', end_time: '17:00' });
  const [editingId, setEditingId] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchShifts = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/voice/shifts/');
      if (response.data.success) {
        setShifts(response.data.shifts);
      }
    } catch (error) {
      console.error('Error fetching shifts:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchShifts();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingId) {
        await axios.put(`http://localhost:8000/api/voice/shifts/${editingId}/update/`, form);
      } else {
        await axios.post('http://localhost:8000/api/voice/shifts/create/', form);
      }
      setForm({ name: '', start_time: '08:00', end_time: '17:00' });
      setEditingId(null);
      fetchShifts();
    } catch (error) {
      console.error('Error saving shift:', error);
      alert('Error saving shift');
    }
  };

  const handleEdit = (shift) => {
    setEditingId(shift.id);
    setForm({
      name: shift.name,
      start_time: shift.start_time,
      end_time: shift.end_time
    });
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this shift?')) return;
    try {
      await axios.delete(`http://localhost:8000/api/voice/shifts/${id}/delete/`);
      fetchShifts();
    } catch (error) {
      console.error('Error deleting shift:', error);
      alert('Error deleting shift');
    }
  };

  if (loading) return <div>Loading shifts...</div>;

  return (
    <div style={{ padding: '24px', backgroundColor: 'white', borderRadius: '16px' }}>
      <h2 style={{ color: 'var(--midnight-green)', marginBottom: '20px' }}> Shift Management</h2>
      
      <form onSubmit={handleSubmit} style={{ marginBottom: '30px', padding: '20px', backgroundColor: '#f8f9fa', borderRadius: '12px' }}>
        <h3>{editingId ? 'Edit Shift' : 'Add New Shift'}</h3>
        <div style={{ display: 'grid', gap: '12px', marginBottom: '16px' }}>
          <input
            type="text"
            placeholder="Shift Name (e.g., Breakfast, Morning, Day)"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            style={{ padding: '10px', borderRadius: '8px', border: '1px solid #ccc' }}
            required
          />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <input
              type="time"
              value={form.start_time}
              onChange={(e) => setForm({ ...form, start_time: e.target.value })}
              style={{ padding: '10px', borderRadius: '8px', border: '1px solid #ccc' }}
              required
            />
            <input
              type="time"
              value={form.end_time}
              onChange={(e) => setForm({ ...form, end_time: e.target.value })}
              style={{ padding: '10px', borderRadius: '8px', border: '1px solid #ccc' }}
              required
            />
          </div>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button type="submit" style={{ padding: '10px 20px', backgroundColor: '#004554', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer' }}>
            {editingId ? 'Update Shift' : 'Add Shift'}
          </button>
          {editingId && (
            <button type="button" onClick={() => { setEditingId(null); setForm({ name: '', start_time: '08:00', end_time: '17:00' }); }} style={{ padding: '10px 20px', backgroundColor: '#6c757d', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer' }}>
              Cancel
            </button>
          )}
        </div>
      </form>

      <div style={{ display: 'grid', gap: '12px' }}>
        <h3>Existing Shifts</h3>
        {shifts.length === 0 && <p>No shifts configured yet.</p>}
        {shifts.map(shift => (
          <div key={shift.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px', backgroundColor: '#f8f9fa', borderRadius: '8px' }}>
            <div>
              <strong>{shift.name}</strong>
              <span style={{ marginLeft: '12px', color: '#666' }}>{shift.start_time} - {shift.end_time}</span>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button onClick={() => handleEdit(shift)} style={{ padding: '5px 12px', backgroundColor: '#004554', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}> Edit</button>
              <button onClick={() => handleDelete(shift.id)} style={{ padding: '5px 12px', backgroundColor: '#004554', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}> Delete</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ShiftManagement;