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

    function finishLoading() {
        loading.value = false;
    }

    async function fetchCurrentUser() {
        console.log('1. Entrando em fetchCurrentUser...');
        if (accessToken.value) {
            try {
                console.log('2. Token de acesso existe. Tentando chamar a API /users/me/');
                const userResponse = await ApiService.getCurrentUser();
                
                // **NOVO LOG:** Vamos ver o que a API realmente retornou
                console.log('3. SUCESSO! A API retornou:', userResponse);
                console.log('4. Os DADOS dentro da resposta são:', userResponse.data);

                currentUserStore.value = userResponse.data;

                console.log('5. Dados do usuário salvos na store com sucesso.');

            } catch (error) {
                // **MUDANÇA CRÍTICA:** Comentamos o logout para poder ver o erro!
                console.error('ERRO INESPERADO! A execução caiu no CATCH. O erro foi:', error);
                // logout(); // Temporariamente desativado para depuração
            }
        } else {
            console.log('fetchCurrentUser foi chamado, mas não há token de acesso.');
        }
    }

    async function login(username, password) {
        console.log('Iniciando o processo de login...');
        const response = await ApiService.getTokens(username, password);
        accessToken.value = response.data.access;
        refreshToken.value = response.data.refresh;
        console.log('Tokens recebidos e salvos.');
        
        await fetchCurrentUser();
    }

    function logout() {
        currentUserStore.value = {};
        accessToken.value = null;
        refreshToken.value = null;
        // window.location.href = '/login'; // Comentado para não atrapalhar
        console.log("Função de LOGOUT foi chamada.");
    }

    return { 
      currentUser, 
      accessToken, 
      isAuthenticated, 
      loading, 
      login, 
      logout, 
      finishLoading, 
      fetchCurrentUser
    };
});