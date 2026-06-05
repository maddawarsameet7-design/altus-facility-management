import axios from 'axios';

const BASE_HOST = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? `http://${window.location.hostname}:8000`
  : `https://api.altsan.com`;

const API_URL = `${BASE_HOST}/api/`;

const api = axios.create({
  baseURL: API_URL,
  timeout: 10000,
});

// Add a request interceptor to include JWT token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('altsan_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Add a response interceptor to handle token expiration
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('altsan_token');
      // Potential redirect to login if we had window access here
    }
    return Promise.reject(error);
  }
);

export const authApi = {
  login: (credentials) => api.post('auth/login/', credentials),
  refresh: (refresh) => api.post('auth/refresh/', { refresh }),
  register: (data) => api.post('auth/register/', data),
};

export const userApi = {
  me: () => api.get('user/me/'),
};

export const dashboardApi = {
  stats: () => api.get('dashboard/stats/'),
};

export const requestApi = {
  getAll: () => api.get('requests/'),
  getById: (id) => api.get(`requests/${id}/`),
  create: (data) => api.post('requests/', data),
  updateStatus: (id, status) => api.post(`requests/${id}/update_status/`, { status }),
  assignWorker: (id, workerId) => api.post(`requests/${id}/assign_worker/`, { worker_id: workerId }),
  sendMessage: (id, content) => api.post(`requests/${id}/send_message/`, { content }),
  processPayment: (id, amount) => api.post(`requests/${id}/process_payment/`, { amount }),
};

export const reviewApi = {
  getByRequest: (requestId) => api.get(`reviews/?request=${requestId}`),
  create: (data) => api.post('reviews/', data),
};

export const workerApi = {
  getAll: () => api.get('workers/'),
  getById: (id) => api.get(`workers/${id}/`),
  updateLocation: (id, lat, lng) => api.patch(`workers/${id}/`, { current_lat: lat, current_lng: lng }),
  pending: () => api.get('workers/pending/'),
  verify: (id, action) => api.post(`workers/${id}/verify/`, { action }),
};

export const categoryApi = {
  getAll: () => api.get('services/'),
};

export default api;
