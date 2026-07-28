import { defineStore } from 'pinia';
import { useStorage } from '@vueuse/core';
import ApiService from '@/service/ApiService';
import { loginRouteForPortal } from '@/constants';
import { computed, ref } from 'vue';

export const useUserStore = defineStore('user', () => {
    const currentUserStore = useStorage('sgdl_user', {});
    const accessToken = useStorage('sgdl_access_token', null);
    const refreshToken = useStorage('sgdl_refresh_token', null);
    const loading = ref(true);

    const isAuthenticated = computed(() => !!accessToken.value);
    const currentUser = computed(() => currentUserStore.value);

    const isGestor = computed(() => currentUser.value?.perfil === 'GESTOR');

    const tipoGestor = computed(
        () => currentUser.value?.vinculo_gestor?.tipo_gestor || currentUser.value?.atuacao_sgdl?.tipo_gestor || null
    );

    /** Gestor Geral — CRUD administrativo pleno (U7). */
    const isGestorGeral = computed(() => {
        if (!isGestor.value) return false;
        if (tipoGestor.value === 'GERAL') return true;
        // Fallback: superuser sem órgão (admin legado / sessão desatualizada)
        const u = currentUser.value;
        return Boolean(u?.is_superuser && !u?.sinapse_orgao_id);
    });

    /** Gestor Setorial — escopo vinculado, sem admin global. */
    const isGestorSetorial = computed(
        () => isGestor.value && !isGestorGeral.value && (tipoGestor.value === 'SETORIAL' || Boolean(currentUser.value?.sinapse_orgao_id))
    );

    function updateCurrentUser(newUserData) {
        currentUserStore.value = { ...currentUserStore.value, ...newUserData };
    }

    function finishLoading() {
        loading.value = false;
    }

    async function fetchCurrentUser() {
        if (accessToken.value) {
            try {
                const userResponse = await ApiService.getCurrentUser();
                currentUserStore.value = userResponse.data;
            } catch (error) {
                console.error('Token inválido ou expirado. Deslogando.', error);
                logout();
            }
        }
    }

    async function login(username, password, rememberMe = false, portal = null) {
        const response = await ApiService.getTokens(username, password, rememberMe, portal);
        accessToken.value = response.data.access;
        refreshToken.value = response.data.refresh;
        await fetchCurrentUser();
    }

    function clearSession() {
        currentUserStore.value = {};
        accessToken.value = null;
        refreshToken.value = null;
    }

    function logout() {
        const portal = localStorage.getItem('sgdl_login_portal') || 'prefeitura';
        currentUserStore.value = {};
        accessToken.value = null;
        refreshToken.value = null;
        window.location.href = loginRouteForPortal(portal);
    }

    return {
        currentUser,
        accessToken,
        isAuthenticated,
        isGestor,
        isGestorGeral,
        isGestorSetorial,
        tipoGestor,
        loading,
        login,
        clearSession,
        logout,
        finishLoading,
        fetchCurrentUser,
        updateCurrentUser
    };
});
