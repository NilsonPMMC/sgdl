import { defineStore } from 'pinia';
import { useStorage } from '@vueuse/core';
import ApiService from '@/service/ApiService';
import { computed, ref } from 'vue';

export const useUserStore = defineStore('user', () => {
    // Agora guardamos o usuário e os tokens
    const user = useStorage('sgdl_user', {});
    const accessToken = useStorage('sgdl_access_token', null);
    const refreshToken = useStorage('sgdl_refresh_token', null);
    const loading = ref(true);

    // Getter para verificar se está autenticado
    const isAuthenticated = computed(() => !!accessToken.value);

    function finishLoading() {
        loading.value = false;
    }

    async function login(username, password) {
        // 1. Pede os tokens para a API
        const response = await ApiService.getTokens(username, password);
        accessToken.value = response.data.access;
        refreshToken.value = response.data.refresh;

        // 2. Com o token, busca os dados do usuário
        const userResponse = await ApiService.getCurrentUser();
        user.value = userResponse.data;
    }

    function logout() {
        user.value = null;
        accessToken.value = null;
        refreshToken.value = null;
        // Redireciona para a tela de login
        window.location.href = '/login';
    }

    return { user, accessToken, isAuthenticated, loading, login, logout, finishLoading };
});