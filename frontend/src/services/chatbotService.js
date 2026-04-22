import axios from 'axios';

const API_HOST = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';
const API_BASE = `http://${API_HOST}:8000/api`;

export const chatbotService = {
  ask: async (question, token) => {
    const response = await axios.post(
      `${API_BASE}/chatbot/query/`,
      { question },
      {
        headers: {
          Authorization: `Bearer ${token || localStorage.getItem('access_token') || ''}`,
        },
      },
    );
    return response.data;
  },
};
