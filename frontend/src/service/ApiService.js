import axios from 'axios';
import { useUserStore } from '@/stores/userStore';

const apiClient = axios.create({
  baseURL: 'http://localhost:8006/api/'
});

apiClient.interceptors.request.use((config) => {
  const userStore = useUserStore();
  const token = userStore.accessToken;
  if (token) {
      config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

export default {
  getTokens(username, password) {
    return apiClient.post('token/', { username, password });
  },
  getCurrentUser() {
    return apiClient.get('users/me/');
  },
  getDashboardStats(params = {}) {
    return apiClient.get('dashboard/stats/', { params });
  },
  getDemandaLocations(params = {}) {
    return apiClient.get('demandas/locations/', { params });
  },
  getDemandas(params = {}) {
      return apiClient.get('demandas/', { params });
  },
  getDemandaById(id) {
      return apiClient.get(`demandas/${id}/`);
  },
  updateDemanda(id, data) {
      return apiClient.put(`demandas/${id}/`, data);
  },
  getServicos() {
    return apiClient.get('servicos/');
  },
  createDemanda(data) {
    return apiClient.post('demandas/', data);
  },
  enviarDemanda(id) {
    return apiClient.post(`demandas/${id}/enviar/`);
  },
  createAnexo(formData) {
    return apiClient.post('anexos/', formData, {
        headers: {
            'Content-Type': 'multipart/form-data'
        }
    });
  },
  deleteDemanda(id) {
      return apiClient.delete(`demandas/${id}/`);
  },
  deleteAnexo(id) {
      return apiClient.delete(`anexos/${id}/`);
  },
  getSecretarias() {
    return apiClient.get('secretarias/');
  },
  despacharDemanda(id, secretariaId) {
    return apiClient.post(`demandas/${id}/despachar/`, { secretaria_id: secretariaId });
  },
  createTramitacao(data) {
    return apiClient.post('tramitacoes/', data);
  },
};