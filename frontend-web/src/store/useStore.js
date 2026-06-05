import { create } from 'zustand';
import { serviceApi } from '../utils/api';

const useStore = create((set, get) => ({
  // Auth State
  user: null,
  setUser: (user) => set({ user }),

  // Service Request State
  requests: [],
  setRequests: (requests) => set({ requests }),
  addRequest: (request) => set((state) => ({ requests: [...state.requests, request] })),
  updateRequest: (id, updates) => set((state) => ({
    requests: state.requests.map(req => req.id === id ? { ...req, ...updates } : req)
  })),

  // Available Services Catalog State
  services: [],
  servicesLoading: false,
  fetchServices: async () => {
    // Avoid re-fetching if already loaded
    if (get().services.length > 0) return;
    
    set({ servicesLoading: true });
    try {
      const res = await serviceApi.list();
      set({ services: res.data, servicesLoading: false });
    } catch (err) {
      console.error("Failed to fetch services", err);
      set({ servicesLoading: false });
    }
  },

  // App-wide loading state
  isLoading: false,
  setIsLoading: (isLoading) => set({ isLoading })
}));

export default useStore;
