import axios from 'axios';

const API_HOST = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';
const API_BASE = `http://${API_HOST}:8000/api`;

const buildHeaders = (token) => ({
  headers: {
    Authorization: `Bearer ${token || localStorage.getItem('access_token') || ''}`,
  },
});

export const mealService = {
  getAll: async (token) => {
    const response = await axios.get(`${API_BASE}/meals/`, buildHeaders(token));
    return response.data;
  },

  create: async (mealData, token) => {
    const response = await axios.post(`${API_BASE}/meals/create/`, mealData, buildHeaders(token));
    return response.data;
  },

  update: async (id, mealData, token) => {
    const response = await axios.put(`${API_BASE}/meals/${id}/`, mealData, buildHeaders(token));
    return response.data;
  },

  delete: async (id, token) => {
    const response = await axios.delete(`${API_BASE}/meals/${id}/`, buildHeaders(token));
    return response.data;
  },
};

export const notificationService = {
  getAll: async (token, options = {}) => {
    const params = new URLSearchParams();
    if (options.unreadOnly) params.set('unread', 'true');
    if (options.incidentOnly) params.set('incident_only', 'true');
    if (options.todayOnly) params.set('today_only', 'true');
    const query = params.toString();
    const endpoint = query ? `${API_BASE}/notifications/?${query}` : `${API_BASE}/notifications/`;
    const response = await axios.get(endpoint, buildHeaders(token));
    return response.data;
  },

  markAsRead: async (id, token) => {
    const response = await axios.post(`${API_BASE}/notifications/${id}/read/`, {}, buildHeaders(token));
    return response.data;
  },

  markAllAsRead: async (token) => {
    const response = await axios.post(`${API_BASE}/notifications/read-all/`, {}, buildHeaders(token));
    return response.data;
  },
};
