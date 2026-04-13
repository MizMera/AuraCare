import axios from 'axios';

const API_BASE = 'http://127.0.0.1:8000/api';

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` }
});

// ========== MEALS ==========
export const mealService = {
  getAll: async () => {
    const response = await axios.get(`${API_BASE}/meals/`, getAuthHeaders());
    return response.data;
  },
  
  create: async (mealData) => {
    const response = await axios.post(`${API_BASE}/meals/create/`, mealData, getAuthHeaders());
    return response.data;
  },
  
  update: async (id, mealData) => {
    const response = await axios.put(`${API_BASE}/meals/${id}/`, mealData, getAuthHeaders());
    return response.data;
  },
  
  delete: async (id) => {
    const response = await axios.delete(`${API_BASE}/meals/${id}/`, getAuthHeaders());
    return response.data;
  }
};

// ========== NOTIFICATIONS ==========
export const notificationService = {
  getAll: async (unreadOnly = false) => {
    const url = unreadOnly ? `${API_BASE}/notifications/?unread=true` : `${API_BASE}/notifications/`;
    const response = await axios.get(url, getAuthHeaders());
    return response.data;
  },
  
  markAsRead: async (id) => {
    const response = await axios.post(`${API_BASE}/notifications/${id}/read/`, {}, getAuthHeaders());
    return response.data;
  },
  
  markAllAsRead: async () => {
    const response = await axios.post(`${API_BASE}/notifications/read-all/`, {}, getAuthHeaders());
    return response.data;
  }
};