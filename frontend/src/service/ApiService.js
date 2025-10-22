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
    return apiClient.patch(`demandas/${id}/`, data);
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
  solicitarTransferencia(demandaId) {
    return apiClient.post(`demandas/${demandaId}/solicitar_transferencia/`);
  },
  aprovarTransferencia(demandaId, novaSecretariaId) {
    return apiClient.post(`demandas/${demandaId}/aprovar_transferencia/`, { nova_secretaria_id: novaSecretariaId });
  },
  atualizarStatusDemanda(demandaId, novoStatus) {
    return apiClient.post(`demandas/${demandaId}/atualizar_status/`, { status: novoStatus });
  },
  getUsuarios(params = {}) {
    return apiClient.get('usuarios/', { params });
  },
  getUserProfile() {
    return apiClient.get('users/me/');
  },
  /**
   * Atualiza os dados do perfil do usuário logado.
   * @param {FormData} formData - Dados do formulário, incluindo o avatar.
   */
  updateUserProfile(formData) {
    return apiClient.patch('users/me/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
  },
  getNotificacoes() {
    return apiClient.get('/notificacoes/');
  },
  marcarNotificacaoComoLida(id) {
    return apiClient.post(`/notificacoes/${id}/marcar_como_lida/`);
  },
  marcarTodasNotificacoesComoLidas() {
    return apiClient.post('/notificacoes/marcar_todas_como_lidas/');
  },
  /**
   * Altera a senha do usuário logado.
   * @param {object} passwordData - { old_password, new_password }.
   */
  changePassword(passwordData) {
    return apiClient.post('users/me/change-password/', passwordData);
  }
};