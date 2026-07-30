import axios from 'axios';
import { useUserStore } from '@/stores/userStore';
import { buildMultipartPayload } from '@/utils/protocoloFormData';

// Puxa a URL do .env, mas se não existir, cai direto na de produção.
const API_URL = import.meta.env.VITE_API_BASE_URL || 'https://sgdl.mogidascruzes.sp.gov.br/api/';

const apiClient = axios.create({
    baseURL: API_URL
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
        const statusCode = error?.response?.status;

        if (statusCode === 401 && originalRequest.url !== 'token/refresh/' && originalRequest.url !== 'token/') {
            const userStore = useUserStore();

            if (userStore.refreshToken) {
                try {
                    const response = await apiClient.post('token/refresh/', {
                        refresh: userStore.refreshToken
                    });

                    const newAccessToken = response.data.access;

                    userStore.accessToken = newAccessToken;

                    originalRequest.headers['Authorization'] = `Bearer ${newAccessToken}`;
                    return apiClient(originalRequest);
                } catch (refreshError) {
                    userStore.logout();
                    window.location.href = '/login';
                    return Promise.reject(refreshError);
                }
            } else {
                userStore.logout();
                window.location.href = '/login';
            }
        }
        return Promise.reject(error);
    }
);

export default {
    getTokens(username, password, rememberMe = false, portal = null) {
        const payload = { username, password, remember_me: rememberMe };
        if (portal) {
            payload.portal = portal;
        }
        return apiClient.post('token/', payload);
    },
    getCurrentUser() {
        return apiClient.get('users/me/');
    },
    getDashboardStats(params = {}) {
        return apiClient.get('dashboard/stats/', { params });
    },
    listarRecusasCopiloto(params = {}) {
        return apiClient.get('copiloto/recusas/', { params });
    },
    getDemandaLocations(params = {}) {
        return apiClient.get('demandas/locations/', { params });
    },
    getMapaAgregacao(params = {}) {
        return apiClient.get('demandas/mapa/agregacao/', { params });
    },
    getDemandas(params = {}) {
        return apiClient.get('demandas/', {
            params,
            paramsSerializer: {
                indexes: null
            }
        });
    },
    acompanharDemanda(id, payload = {}) {
        return apiClient.post(`demandas/${id}/acompanhar/`, payload);
    },
    desacompanharDemanda(id) {
        return apiClient.post(`demandas/${id}/desacompanhar/`);
    },
    getDemandasResumoFilas() {
        return apiClient.get('demandas/resumo-filas/');
    },
    getDemandaById(id) {
        return apiClient.get(`demandas/${id}/`);
    },
    updateDemanda(id, data) {
        return apiClient.patch(`demandas/${id}/`, data);
    },
    getServicos(params = {}) {
        return apiClient.get('servicos/', { params });
    },
    createDemanda(data) {
        return apiClient.post('demandas/', data);
    },
    enviarDemanda(id, payload = {}) {
        return apiClient.post(`demandas/${id}/enviar/`, payload);
    },
    previewEnvioLote(demandaIds) {
        return apiClient.post('demandas/preview-envio-lote/', { demanda_ids: demandaIds });
    },
    enviarDemandasLote(payload) {
        return apiClient.post('demandas/enviar-lote/', payload);
    },

    previewEnvioOficial(id) {
        return apiClient.get(`demandas/${id}/preview-envio-oficial/`);
    },

    previewEnvioOficialPdf(id) {
        return apiClient.get(`demandas/${id}/preview-envio-oficial-pdf/`, {
            responseType: 'blob'
        });
    },

    getNumeracaoIndicacao() {
        return apiClient.get('indicacoes/numeracao/');
    },

    atualizarNumeracaoIndicacao(payload) {
        return apiClient.patch('indicacoes/numeracao/', payload);
    },

    getConfiguracaoOficio() {
        return apiClient.get('configuracao-oficio/');
    },

    updateConfiguracaoOficio(data) {
        // FormData: não definir Content-Type — o axios inclui o boundary automaticamente.
        return apiClient.patch('configuracao-oficio/', data);
    },

    previewConfiguracaoOficioPdf(formData) {
        return apiClient.post('configuracao-oficio/preview-pdf/', formData, {
            responseType: 'blob'
        });
    },

    getConfiguracaoCarta() {
        return apiClient.get('configuracao-carta/');
    },

    updateConfiguracaoCarta(payload) {
        return apiClient.patch('configuracao-carta/', payload);
    },

    validarAssinatura(codigo) {
        return apiClient.get(`v1/validar-assinatura/${codigo}/`);
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
    getConsultaHub() {
        return apiClient.get('consulta/hub/');
    },

    buscarConsultaHub(params = {}) {
        return apiClient.get('consulta/busca/', { params });
    },

    getCartaServicos(params = {}) {
        return apiClient.get('integrations/carta/servicos/', { params });
    },
    getCartaServicoDetalhe(servicoId) {
        return apiClient.get(`integrations/carta/servicos/${servicoId}/`);
    },
    simularTriagemCarta({ texto, top_k = 5 }) {
        return apiClient.post('integrations/carta/simular-triagem/', { texto, top_k });
    },

    getCartaOtimizadaServicos(params = {}) {
        return apiClient.get('carta-otimizada/', { params });
    },
    getCartaOtimizadaServico(id) {
        return apiClient.get(`carta-otimizada/${id}/`);
    },
    getCartaOtimizadaEstatisticas() {
        return apiClient.get('carta-otimizada/estatisticas/');
    },
    getCartaOtimizadaComparacaoScores() {
        return apiClient.get('carta-otimizada/comparacao_scores/');
    },
    getCartaOtimizadaProblemasComuns() {
        return apiClient.get('carta-otimizada/problemas_comuns/');
    },
    despacharDemanda(id, despachoData, arquivos = []) {
        const { body } = buildMultipartPayload(despachoData, arquivos);
        return apiClient.post(`demandas/${id}/despachar/`, body);
    },
    previewDespachoDemanda(id, payload) {
        return apiClient.post(`demandas/${id}/preview-despacho/`, payload);
    },
    previewConclusaoSecretaria(demandaId, payload) {
        return apiClient.post(`demandas/${demandaId}/preview-conclusao-secretaria/`, payload);
    },
    previewDespachoDevolutiva(demandaId, payload) {
        return apiClient.post(`demandas/${demandaId}/preview-despacho-devolutiva/`, payload);
    },
    getEstadoOperacional(demandaId) {
        return apiClient.get(`demandas/${demandaId}/operacional/estado/`);
    },
    getHistoricoTecnicoOperacional(demandaId) {
        return apiClient.get(`demandas/${demandaId}/operacional/historico-tecnico/`);
    },
    vincularServicoOperacional(demandaId, sinapseServicoId) {
        return apiClient.post(`demandas/${demandaId}/operacional/vincular-servico/`, {
            sinapse_servico_id: sinapseServicoId
        });
    },
    recusaProtocoloOperacional(demandaId, payload) {
        return apiClient.post(`demandas/${demandaId}/operacional/recusa-protocolo/`, payload);
    },
    conclusaoParcialOperacional(demandaId, payload, arquivos = []) {
        const { body } = buildMultipartPayload(payload, arquivos);
        return apiClient.post(`demandas/${demandaId}/operacional/conclusao-parcial/`, body);
    },
    iniciarExecucaoOperacional(demandaId) {
        return apiClient.post(`demandas/${demandaId}/operacional/iniciar-execucao/`);
    },
    abrirPernasTransversal(demandaId, payload) {
        return apiClient.post(`demandas/${demandaId}/operacional/abrir-pernas-transversal/`, payload);
    },
    scatterGatherOperacional(demandaId, payload, multipart = false) {
        const config = multipart ? { headers: { 'Content-Type': 'multipart/form-data' } } : {};
        return apiClient.post(`demandas/${demandaId}/operacional/scatter-gather/`, payload, config);
    },
    nosUnificadosOperacional(demandaId, payload, multipart = false) {
        const config = multipart ? { headers: { 'Content-Type': 'multipart/form-data' } } : {};
        return apiClient.post(`demandas/${demandaId}/operacional/nos-unificados/`, payload, config);
    },
    conclusaoTecnicaOperacional(demandaId, payload) {
        return apiClient.post(`demandas/${demandaId}/operacional/conclusao-tecnica/`, payload);
    },
    devolverProtocoloOperacional(demandaId, payload) {
        return apiClient.post(`demandas/${demandaId}/operacional/devolver-protocolo/`, payload);
    },
    previewConclusaoFinalOperacional(demandaId, payload) {
        return apiClient.post(`demandas/${demandaId}/operacional/preview-conclusao-final/`, payload);
    },
    conclusaoFinalOperacional(demandaId, payload, arquivos = []) {
        const { body } = buildMultipartPayload(payload, arquivos);
        return apiClient.post(`demandas/${demandaId}/operacional/conclusao-final/`, body);
    },
    getGestoresProtocolo() {
        return apiClient.get('demandas/gestores-protocolo/');
    },
    listarAssinaturasValidacaoPendentes() {
        return apiClient.get('assinaturas-validacao/pendentes/');
    },
    previewValidacaoAssinaturaGestor(validacaoId) {
        return apiClient.post(`assinaturas-validacao/${validacaoId}/preview/`, {});
    },
    validarAssinaturaGestor(validacaoId, payload) {
        return apiClient.post(`assinaturas-validacao/${validacaoId}/validar/`, payload);
    },
    createTramitacao(data) {
        return apiClient.post('tramitacoes/', data);
    },
    atualizarTramitacao(id, data) {
        return apiClient.patch(`tramitacoes/${id}/`, data);
    },
    excluirTramitacao(id) {
        return apiClient.delete(`tramitacoes/${id}/`);
    },
    otimizarTextoTramitacao(payload) {
        return apiClient.post('v1/tramitacao/otimizar-texto/', payload, { timeout: 60000 });
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
        return apiClient.get('notificacoes/');
    },
    marcarNotificacaoComoLida(id) {
        return apiClient.post(`notificacoes/${id}/marcar_como_lida/`);
    },
    marcarTodasNotificacoesComoLidas() {
        return apiClient.post('notificacoes/marcar_todas_como_lidas/');
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
    getReportProcessMiningSetor(params) {
        return apiClient.get('/reports/process-mining-setor/', { params });
    },
    getReportFunilStatus(params) {
        return apiClient.get('/reports/funil-status/', { params });
    },
    getReportComparativoVereador(params) {
        return apiClient.get('/reports/comparativo-vereador/', { params });
    },
    async exportReportCSV(params) {
        const response = await apiClient.get('/reports/export-csv/', {
            params,
            responseType: 'blob'
        });
        const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/csv;charset=utf-8;' }));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `relatorio_demandas_${new Date().toISOString().slice(0, 10)}.csv`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
        return response;
    },
    buscarCepGeocoding(cep) {
        const limpo = String(cep || '').replace(/\D/g, '');
        return apiClient.get('v1/geocoding/cep/', { params: { cep: limpo } });
    },

    buscarLogradouros(termo, bairro = null, limit = 8) {
        const params = { q: termo, limit };
        if (bairro) {
            params.bairro = bairro;
        }
        return apiClient.get('v1/geocoding/logradouros/', { params });
    },

    resolverGeocodingEndereco(payload) {
        return apiClient.post('v1/geocoding/resolver/', payload);
    },

    reverseGeocodingEndereco({ latitude, longitude }) {
        return apiClient.post('v1/geocoding/reverse/', { latitude, longitude });
    },

    getSinapseSyncHealth() {
        return apiClient.get('integrations/sinapse/sync-health/');
    },
    getSinapseUnmatched(params = {}) {
        return apiClient.get('integrations/sinapse/unmatched/', { params });
    },
    bindSinapseManual(payload) {
        return apiClient.post('integrations/sinapse/bind-manual/', payload);
    },
    bindSinapseManualBulk(bindings = []) {
        return apiClient.post('integrations/sinapse/bind-manual-bulk/', { bindings });
    },

    /**
     * Copiloto conversacional (slot filling + Sinapse).
     * @param {{ mensagem: string, session_id?: string|null }} payload
     */
    confirmarServicoCopiloto({ session_id, indice_demanda, sinapse_servico_id }) {
        return apiClient.post('v1/chat/confirmar-servico/', {
            session_id,
            indice_demanda,
            sinapse_servico_id
        });
    },

    retriagemCartaCopiloto({ session_id, indice_demanda }) {
        return apiClient.post('v1/chat/retriagem-carta/', { session_id, indice_demanda });
    },

    ignorarServicoCopiloto({ session_id, indice_demanda }) {
        return apiClient.post('v1/chat/ignorar-servico/', { session_id, indice_demanda });
    },

    atualizarLocalizacaoCopiloto({
        session_id,
        indice_demanda,
        latitude,
        longitude,
        fonte,
        confirmar_local
    }) {
        const payload = {
            session_id,
            indice_demanda,
            latitude,
            longitude
        };
        if (fonte != null) payload.fonte = fonte;
        if (confirmar_local != null) payload.confirmar_local = confirmar_local;
        return apiClient.post('v1/chat/atualizar-localizacao/', payload);
    },

    marcarDemandaCopiloto({ session_id, indice_demanda, aprovado_final, descartada }) {
        return apiClient.post('v1/chat/marcar-demanda/', {
            session_id,
            indice_demanda,
            aprovado_final,
            descartada
        });
    },

    atualizarIndicacaoCopiloto(payload) {
        return apiClient.post('v1/chat/atualizar-indicacao/', payload);
    },

    confirmarTendenciaCopiloto(payload) {
        return apiClient.post('v1/chat/confirmar-tendencia/', payload);
    },

    revisarEtapaCopiloto({ session_id, indice_demanda, etapa }) {
        return apiClient.post('v1/chat/revisar-etapa/', {
            session_id,
            indice_demanda,
            etapa
        });
    },

    editarPedidoCopiloto({ session_id, indice_demanda, titulo, descricao, pedido_integral }) {
        return apiClient.post('v1/chat/editar-pedido/', {
            session_id,
            indice_demanda,
            titulo,
            descricao,
            pedido_integral
        });
    },

    editarLocalCopiloto({ session_id, indice_demanda, endereco }) {
        return apiClient.post('v1/chat/editar-local/', {
            session_id,
            indice_demanda,
            endereco
        });
    },

    removerAnexoSessaoCopiloto({ session_id, indice_sessao }) {
        return apiClient.post('v1/chat/remover-anexo-sessao/', {
            session_id,
            indice_sessao
        });
    },

    buscarTendenciasSimilares({ texto, limite = 5 }) {
        return apiClient.post('tendencias/buscar-similares/', { texto, limite });
    },

    listarTendencias(params = {}) {
        return apiClient.get('tendencias/', { params });
    },

    obterTendencia(id) {
        return apiClient.get(`tendencias/${id}/`);
    },

    listarTendenciaOcorrencias(id) {
        return apiClient.get(`tendencias/${id}/ocorrencias/`);
    },

    atualizarTendencia(id, data) {
        return apiClient.patch(`tendencias/${id}/`, data);
    },

    promoverTendenciaCarta(id, sinapse_servico_id) {
        return apiClient.post(`tendencias/${id}/promover-carta/`, { sinapse_servico_id });
    },

    getClustersResumo(params = {}) {
        return apiClient.get('clusters/resumo-operacional/', { params });
    },

    listarClusters(params = {}) {
        return apiClient.get('clusters/', { params });
    },

    obterCluster(id) {
        return apiClient.get(`clusters/${id}/`);
    },

    listarClusterDemandas(id) {
        return apiClient.get(`clusters/${id}/demandas/`);
    },

    listarDemandasCandidatasCluster(clusterId, params = {}) {
        return apiClient.get(`clusters/${clusterId}/demandas-candidatas/`, { params });
    },

    despacharClusterSuperOs(clusterId, despachoData) {
        return apiClient.post(`clusters/${clusterId}/despachar/`, despachoData);
    },

    vincularDemandaCluster(clusterId, demandaId) {
        return apiClient.post(`clusters/${clusterId}/vincular/`, { demanda_id: demandaId });
    },

    desvincularDemandaCluster(clusterId, demandaId) {
        return apiClient.post(`clusters/${clusterId}/desvincular/`, { demanda_id: demandaId });
    },

    getDemandaClusterElegibilidade(demandaId) {
        return apiClient.get(`demandas/${demandaId}/cluster-elegibilidade/`);
    },

    getClusterSituacaoAderencia(demandaId) {
        return apiClient.get(`demandas/${demandaId}/cluster-situacao-aderencia/`);
    },

    aderirClusterLider(demandaId) {
        return apiClient.post(`demandas/${demandaId}/cluster-aderir-lider/`);
    },

    desvincularDemandaClusterIndividual(demandaId) {
        return apiClient.post(`demandas/${demandaId}/cluster-desvincular/`);
    },

    listarFluxoServicosCarta(params = {}) {
        return apiClient.get('fluxo-servicos/carta/', { params });
    },

    upsertFluxoServico(payload) {
        return apiClient.post('fluxo-servicos/upsert/', payload);
    },

    upsertCartaSetor(payload) {
        return apiClient.post('carta-setores/upsert/', payload);
    },

    listarAssuntosCarta(params = {}) {
        return apiClient.get('assuntos-carta/', { params });
    },

    atualizarAssuntoCarta(id, payload) {
        return apiClient.patch(`assuntos-carta/${id}/`, payload);
    },

    listarTextosPadraoDespacho(params = {}) {
        return apiClient.get('textos-padrao-despacho/', { params });
    },

    criarTextoPadraoDespacho(payload) {
        return apiClient.post('textos-padrao-despacho/', payload);
    },

    atualizarTextoPadraoDespacho(id, payload) {
        return apiClient.patch(`textos-padrao-despacho/${id}/`, payload);
    },

    excluirTextoPadraoDespacho(id) {
        return apiClient.delete(`textos-padrao-despacho/${id}/`);
    },

    aplicarTextoPadraoDespacho(id, payload = {}) {
        return apiClient.post(`textos-padrao-despacho/${id}/aplicar/`, payload);
    },

    metaCriacaoTextoPadraoDespacho() {
        return apiClient.get('textos-padrao-despacho/meta-criacao/');
    },

    upsertCartaAssunto(payload) {
        return apiClient.post('carta-assuntos/upsert/', payload);
    },

    listarDeParaRmSinapse() {
        return apiClient.get('depara-rm-sinapse/');
    },

    atualizarDeParaRmSinapse(id, payload) {
        return apiClient.patch(`depara-rm-sinapse/${id}/`, payload);
    },

    importarUnidadesRm(payload = {}) {
        return apiClient.post('unidades-administrativas/importar-rm/', payload);
    },

    carregarDeParaRmCsv() {
        return apiClient.post('depara-rm-sinapse/carregar-csv/');
    },

    listarUnidadesAdministrativas(params = {}) {
        return apiClient.get('unidades-administrativas/', { params });
    },

    listarOrgaosSetores() {
        return apiClient.get('unidades-administrativas/orgaos/');
    },

    criarUnidadeAdministrativa(payload) {
        return apiClient.post('unidades-administrativas/', payload);
    },

    atualizarUnidadeAdministrativa(id, payload) {
        return apiClient.patch(`unidades-administrativas/${id}/`, payload);
    },

    vincularResponsavelSetor(unidadeId, payload) {
        return apiClient.post(`unidades-administrativas/${unidadeId}/responsaveis/`, payload);
    },

    desvincularResponsavelSetor(unidadeId, payload) {
        return apiClient.post(`unidades-administrativas/${unidadeId}/desvincular-responsavel/`, payload);
    },

    getVinculosSetor(unidadeId) {
        return apiClient.get(`unidades-administrativas/${unidadeId}/vinculos/`);
    },

    excluirUnidadeAdministrativa(unidadeId, payload = {}) {
        return apiClient.post(`unidades-administrativas/${unidadeId}/excluir/`, payload);
    },

    listarGestaoUsuarios(params = {}) {
        return apiClient.get('gestao-usuarios/', { params });
    },

    criarGestaoUsuario(payload) {
        return apiClient.post('gestao-usuarios/', payload);
    },

    atualizarGestaoUsuario(id, payload) {
        return apiClient.patch(`gestao-usuarios/${id}/`, payload);
    },

    listarGestaoUsuariosSecretaria(params = {}) {
        return apiClient.get('gestao-usuarios-secretaria/', { params });
    },

    criarGestaoUsuarioSecretaria(payload) {
        return apiClient.post('gestao-usuarios-secretaria/', payload);
    },

    atualizarGestaoUsuarioSecretaria(id, payload) {
        return apiClient.patch(`gestao-usuarios-secretaria/${id}/`, payload);
    },

    listarGestaoUsuariosGestor(params = {}) {
        return apiClient.get('gestao-usuarios-gestor/', { params });
    },

    criarGestaoUsuarioGestor(payload) {
        return apiClient.post('gestao-usuarios-gestor/', payload);
    },

    atualizarGestaoUsuarioGestor(id, payload) {
        return apiClient.patch(`gestao-usuarios-gestor/${id}/`, payload);
    },

    encaminharDemandaSetor(demandaId, payload) {
        return apiClient.post(`demandas/${demandaId}/encaminhar-setor/`, payload);
    },

    solicitarDevolutiva(demandaId, payload) {
        return apiClient.post(`demandas/${demandaId}/solicitar-devolutiva/`, payload);
    },

    listEstudosViabilidade(params = {}) {
        return apiClient.get('estudos-viabilidade/', { params });
    },

    despacharDevolutiva(demandaId, payload, arquivos = []) {
        const { body } = buildMultipartPayload(payload, arquivos);
        return apiClient.post(`demandas/${demandaId}/despachar-devolutiva/`, body);
    },

    encerrarDevolutiva(demandaId) {
        return apiClient.post(`demandas/${demandaId}/encerrar-devolutiva/`, {});
    },

    getPacoteDevolutiva(demandaId) {
        return apiClient.get(`demandas/${demandaId}/pacote-devolutiva/`);
    },

    getAnexosOperacionais(demandaId) {
        return apiClient.get(`demandas/${demandaId}/anexos-operacionais/`);
    },

    getAnexosOperacionais(demandaId) {
        return apiClient.get(`demandas/${demandaId}/anexos-operacionais/`);
    },

    previewRespostaCidadao(demandaId, texto = '') {
        return apiClient.get(`demandas/${demandaId}/preview-resposta-cidadao/`, {
            params: texto ? { texto } : {},
            responseType: 'blob'
        });
    },

    confirmarCiencia(demandaId, payload) {
        return apiClient.post(`demandas/${demandaId}/confirmar-ciencia/`, payload);
    },

    listarCopilotoFaq(params = {}) {
        return apiClient.get('copiloto-faq/', { params });
    },

    obterCopilotoFaq(id) {
        return apiClient.get(`copiloto-faq/${id}/`);
    },

    criarCopilotoFaq(data) {
        return apiClient.post('copiloto-faq/', data);
    },

    atualizarCopilotoFaq(id, data) {
        return apiClient.patch(`copiloto-faq/${id}/`, data);
    },

    listarCopilotoFaqPadroes(params = {}) {
        return apiClient.get('copiloto-faq-padroes/', { params });
    },

    criarCopilotoFaqPadrao(data) {
        return apiClient.post('copiloto-faq-padroes/', data);
    },

    excluirCopilotoFaqPadrao(id) {
        return apiClient.delete(`copiloto-faq-padroes/${id}/`);
    },

    /** Preview Groq (dry-run) — curadoria FAQ sem gravar. */
    buscarSugestoesFaqLLM(foco = '') {
        const params = {};
        if (foco && String(foco).trim()) {
            params.foco = String(foco).trim();
        }
        return apiClient.get('v1/copiloto-faq/sugestoes-llm/', { params, timeout: 120000 });
    },

    /** Aprova e persiste uma sugestão da curadoria FAQ. */
    aprovarSugestaoFaq(payload) {
        return apiClient.post('v1/copiloto-faq/enriquecer-llm/', payload);
    },

    /** Atalhos de pedidos frequentes (corpus legado — aprendizado). */
    corpusLegadoAtalhosCopiloto(limite = 12) {
        return apiClient.get('v1/corpus-legado/atalhos-copiloto/', { params: { limite } });
    },

    /** Detalhamento de pedido frequente — opções na carta Sinapse. */
    corpusLegadoAtalhoDetalhe(eixoId) {
        return apiClient.get('v1/corpus-legado/atalho-detalhe/', { params: { id: eixoId } });
    },

    interagirCopiloto(payload) {
        const anexos = payload.anexos;
        if (anexos && anexos.length > 0) {
            const formData = new FormData();
            formData.append('mensagem', payload.mensagem || '');
            if (payload.session_id) {
                formData.append('session_id', payload.session_id);
            }
            if (payload.indices_aprovados?.length) {
                formData.append('indices_aprovados', payload.indices_aprovados.join(','));
            }
            if (payload.corpus_sinapse_servico_id != null) {
                formData.append('corpus_sinapse_servico_id', String(payload.corpus_sinapse_servico_id));
            }
            if (payload.corpus_atalho_id) {
                formData.append('corpus_atalho_id', payload.corpus_atalho_id);
            }
            for (const arquivo of anexos) {
                formData.append('anexos', arquivo);
            }
            const indices = payload.anexo_demanda_indices;
            if (Array.isArray(indices) && indices.length === anexos.length) {
                formData.append(
                    'anexo_demanda_indices',
                    indices.map((v) => (v === null || v === undefined ? '' : String(v))).join(',')
                );
            }
            return apiClient.post('v1/chat/interagir/', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
        }
        const body = { mensagem: payload.mensagem };
        if (payload.session_id) {
            body.session_id = payload.session_id;
        }
        if (payload.indices_aprovados?.length) {
            body.indices_aprovados = payload.indices_aprovados.join(',');
        }
        if (payload.corpus_sinapse_servico_id != null) {
            body.corpus_sinapse_servico_id = payload.corpus_sinapse_servico_id;
        }
        if (payload.corpus_atalho_id) {
            body.corpus_atalho_id = payload.corpus_atalho_id;
        }
        return apiClient.post('v1/chat/interagir/', body);
    }
};
