import { create } from 'zustand';
import { serviceApi, societyApi, userApi } from '../utils/api';

const useStore = create((set, get) => ({
  // Auth State
  user: null,
  setUser: (user) => set({ user }),

  // Multi-Tenancy / Society State
  currentSociety: (() => {
    try {
      return JSON.parse(localStorage.getItem('altsan_current_society') || 'null');
    } catch {
      return null;
    }
  })(),
  memberships: [],
  societies: [],
  setCurrentSociety: (society) => {
    if (society) {
      localStorage.setItem('altsan_current_society', JSON.stringify(society));
    } else {
      localStorage.removeItem('altsan_current_society');
    }
    set({ currentSociety: society });
  },
  setMemberships: (memberships) => set({ memberships }),
  setSocieties: (societies) => set({ societies }),

  fetchUserSocieties: async () => {
    try {
      const meRes = await userApi.me();
      const userData = meRes.data;
      set({ user: userData, memberships: userData.memberships || [] });

      // If user has societies list endpoint access (Director or Member with active societies)
      const socRes = await societyApi.list();
      const socList = Array.isArray(socRes.data) ? socRes.data : (socRes.data?.results || []);
      set({ societies: socList });

      // If no current society selected, select the first active membership society
      const current = get().currentSociety;
      if (!current && userData.memberships && userData.memberships.length > 0) {
        const activeM = userData.memberships.find(m => m.is_active) || userData.memberships[0];
        const selected = {
          id: activeM.society,
          name: activeM.society_name,
          role: activeM.role,
          client_type: activeM.client_type,
          is_active: activeM.is_active
        };
        get().setCurrentSociety(selected);
      } else if (!current && socList.length > 0 && userData.role === 'DIRECTOR') {
        const selected = {
          id: socList[0].id,
          name: socList[0].name,
          role: 'DIRECTOR',
          client_type: socList[0].client_type,
          is_active: true
        };
        get().setCurrentSociety(selected);
      }
    } catch (err) {
      console.warn("Could not fetch user societies", err);
    }
  },

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
      const rawList = Array.isArray(res.data) ? res.data : (res.data?.results || []);
      set({ services: rawList, servicesLoading: false });
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
