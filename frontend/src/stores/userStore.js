import { defineStore } from 'pinia';
import { useStorage } from '@vueuse/core';
import ApiService from '@/service/ApiService';
import { computed, ref } from 'vue';

export const useUserStore = defineStore('user', () => {
    const currentUserStore = useStorage('sgdl_user', {}); 
    const accessToken = useStorage('sgdl_access_token', null);
    const refreshToken = useStorage('sgdl_refresh_token', null);
    const loading = ref(true);

    const isAuthenticated = computed(() => !!accessToken.value);
    const currentUser = computed(() => currentUserStore.value);

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
                console.error("Token inválido ou expirado. Deslogando.", error);
                logout();
            }
        }
    }

    async function login(username, password, rememberMe = false) {
        const response = await ApiService.getTokens(username, password, rememberMe);
        accessToken.value = response.data.access;
        refreshToken.value = response.data.refresh;        
        await fetchCurrentUser();
    }

    function logout() {
        currentUserStore.value = {};
        accessToken.value = null;
        refreshToken.value = null;
        window.location.href = '/login';
    }

    return { 
      currentUser, 
      accessToken, 
      isAuthenticated, 
      loading, 
      login, 
      logout, 
      finishLoading, 
      fetchCurrentUser,
      updateCurrentUser
    };
});