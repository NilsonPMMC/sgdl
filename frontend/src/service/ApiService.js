import axios from 'axios';
import { useUserStore } from '@/stores/userStore';

const apiClient = axios.create({
  baseURL: 'https://sgdl.mogidascruzes.sp.gov.br/api/'
});

apiClient.interceptors.request.use(
  (config) => {
      const userStore = useUserStore();
      const token = userStore.accessToken;
      if (token) {
          config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
  },
  (error) => {
      return Promise.reject(error);
  }
);

apiClient.interceptors.response.use(
  (response) => {
      return response;
  },
  async (error) => {
      const originalRequest = error.config;

      if (error.response.status === 401 && 
          originalRequest.url !== 'token/refresh/' &&
          originalRequest.url !== 'token/'
          ) {
          
          const userStore = useUserStore();

          if (userStore.refreshToken) {
              try {
                  console.log('Access token expirado. Tentando refresh...');
                  
                  const response = await apiClient.post('token/refresh/', {
                      refresh: userStore.refreshToken
                  });
                  
                  const newAccessToken = response.data.access;
                  
                  userStore.accessToken = newAccessToken;
                  
                  originalRequest.headers['Authorization'] = `Bearer ${newAccessToken}`;
                  return apiClient(originalRequest);

              } catch (refreshError) {
                  console.error('Refresh token é inválido. Deslogando.', refreshError);
                  userStore.logout();
                  window.location.href = '/login';
                  return Promise.reject(refreshError);
              }
          } else {
              console.error('Sem refresh token disponível. Deslogando.');
              userStore.logout();
              window.location.href = '/login';
          }
      }
      return Promise.reject(error);
  }
);

export default {
  getTokens(username, password, rememberMe = false) {
    return apiClient.post('token/', { username, password, remember_me: rememberMe });
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
  despacharDemanda(id, despachoData) {
    return apiClient.post(`demandas/${id}/despachar/`, despachoData);
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
  },
  requestPasswordReset(data) {
    return apiClient.post('password-reset/', data);
  },
  confirmPasswordReset(data) {
    return apiClient.post('password-reset-confirm/', data);
  },
  
  /**
     * Busca dados agregados para os relatórios.
     * @param {object} params - Objeto com os filtros (data_inicio, status__in, etc.)
     */
  getReportKPIs(params) {
    return apiClient.get('/reports/kpis/', { params });
  },
  getReportPorStatus(params) {
    return apiClient.get('/reports/por-status/', { params }); // CORRIGIDO
  },
  getReportPorSecretaria(params) {
    return apiClient.get('/reports/por-secretaria/', { params }); // CORRIGIDO
  },
  getReportPorVereador(params) {
    return apiClient.get('/reports/por-vereador/', { params }); // CORRIGIDO
  },
  getReportHeatmap(params) {
    return apiClient.get('/reports/heatmap/', { params }); // CORRIGIDO
  },
  getReportDemandasList(params) {
    return apiClient.get('/reports/demandas-filtradas/', { params });
  },
};