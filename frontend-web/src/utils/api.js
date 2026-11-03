import axios from 'axios';

/**
 * Resolves the backend API base URL strictly adhering to environment rules:
 * - In Development (import.meta.env.DEV):
 *   Prefers VITE_API_URL if provided, else falls back to local host detection.
 * - In Production (!import.meta.env.DEV):
 *   VITE_API_URL MUST be configured. Fails loudly with an explicit Error if missing.
 *   Never guesses or hardcodes a production domain.
 */
export function resolveApiBaseUrl() {
  const envUrl = import.meta.env.VITE_API_URL;

  if (import.meta.env.DEV) {
    if (envUrl) {
      return envUrl.endsWith('/') ? envUrl : `${envUrl}/`;
    }
    const hostname = (typeof window !== 'undefined' && window.location?.hostname) 
      ? window.location.hostname 
      : 'localhost';
    return `http://${hostname}:8000/api/`;
  }

  // Production check
  if (!envUrl) {
    throw new Error(
      '[Altsan Security Error] Missing required environment variable VITE_API_URL in production build. ' +
      'Refusing to guess production domain.'
    );
  }

  return envUrl.endsWith('/') ? envUrl : `${envUrl}/`;
}

export const API_URL = resolveApiBaseUrl();

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

export const serviceApi = {
  list: () => api.get('services/'),
};

export const categoryApi = serviceApi;

export const paymentApi = {
  createOrder: (data) => api.post('payments/create-order/', data),
  verify: (data) => api.post('payments/verify/', data),
};

export const societyApi = {
  list: () => api.get('societies/'),
  getById: (id) => api.get(`societies/${id}/`),
  create: (data) => api.post('societies/', data),
  update: (id, data) => api.put(`societies/${id}/`, data),
  delete: (id) => api.delete(`societies/${id}/`),
  createInvite: (societyId, data) => api.post(`societies/${societyId}/invite/`, data),
  getMembers: (societyId, pendingOnly = false) => api.get(`societies/${societyId}/members/${pendingOnly ? '?pending=true' : ''}`),
  approveMember: (societyId, userId) => api.post(`societies/${societyId}/members/${userId}/approve/`),
  rejectMember: (societyId, userId) => api.post(`societies/${societyId}/members/${userId}/reject/`),
  addSupervisor: (societyId, userId) => api.post(`societies/${societyId}/supervisors/`, { user_id: userId }),
  removeSupervisor: (societyId, userId) => api.delete(`societies/${societyId}/supervisors/${userId}/`),
  join: (code) => api.post('societies/join/', { code }),

  // Sites
  getSites: () => api.get('sites/'),
  createSite: (data) => api.post('sites/', data),
  updateSite: (id, data) => api.put(`sites/${id}/`, data),
  deleteSite: (id) => api.delete(`sites/${id}/`),

  // Settings
  getSettings: (societyId) => api.get(`society-settings/${societyId}/`),
  updateSettings: (societyId, data) => api.put(`society-settings/${societyId}/`, data),
};

export default api;
