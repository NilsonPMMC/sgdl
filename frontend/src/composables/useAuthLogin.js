import { onMounted, ref } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useUserStore } from '@/stores/userStore';
import ApiService from '@/service/ApiService';
import { loginRouteForPortal, PORTAL_AUTH, rotaHomePorPerfil } from '@/constants';

const PORTAL_STORAGE_KEY = 'sgdl_login_portal';

function extrairErroPortal(err) {
    const data = err?.response?.data;
    if (!data) return null;
    const code = Array.isArray(data.code) ? data.code[0] : data.code;
    if (code === 'wrong_portal') {
        const portalCorreto = Array.isArray(data.portal_correto)
            ? data.portal_correto[0]
            : data.portal_correto;
        const portalLabel = Array.isArray(data.portal_label) ? data.portal_label[0] : data.portal_label;
        const detail = Array.isArray(data.detail) ? data.detail[0] : data.detail;
        return {
            message: detail || 'Esta conta não pertence a este portal.',
            redirectRoute: loginRouteForPortal(portalCorreto),
            redirectLabel: portalLabel || PORTAL_AUTH[portalCorreto]?.label || 'portal correto'
        };
    }
    const detail = Array.isArray(data.detail) ? data.detail[0] : data.detail;
    if (typeof detail === 'string' && detail.toLowerCase().includes('portal')) {
        return { message: detail, redirectRoute: null, redirectLabel: null };
    }
    return null;
}

export function useAuthLogin(portal) {
    const router = useRouter();
    const route = useRoute();
    const userStore = useUserStore();

    const username = ref('');
    const password = ref('');
    const error = ref(null);
    const portalRedirect = ref(null);
    const portalRedirectLabel = ref(null);
    const rememberMe = ref(false);
    const submitting = ref(false);

    const showResetPasswordDialog = ref(false);
    const resetEmail = ref('');
    const resetSuccess = ref(false);
    const resetError = ref(null);
    const resetLoading = ref(false);

    onMounted(() => {
        if (localStorage.getItem('sgdlRememberMePref') === 'true') {
            rememberMe.value = true;
            const rememberedUser = localStorage.getItem('sgdlRememberedUser');
            if (rememberedUser) {
                username.value = rememberedUser;
            }
        }
    });

    const persistRememberMe = () => {
        if (rememberMe.value) {
            localStorage.setItem('sgdlRememberMePref', 'true');
            localStorage.setItem('sgdlRememberedUser', username.value);
        } else {
            localStorage.removeItem('sgdlRememberMePref');
            localStorage.removeItem('sgdlRememberedUser');
        }
    };

    const limparErro = () => {
        error.value = null;
        portalRedirect.value = null;
        portalRedirectLabel.value = null;
    };

    const handleLogin = async () => {
        limparErro();
        submitting.value = true;
        persistRememberMe();

        try {
            await userStore.login(username.value, password.value, rememberMe.value, portal);
            localStorage.setItem(PORTAL_STORAGE_KEY, portal);
            await router.push(rotaHomePorPerfil(userStore.currentUser?.perfil));
        } catch (err) {
            userStore.clearSession();
            const portalErr = extrairErroPortal(err);
            if (portalErr) {
                error.value = portalErr.message;
                portalRedirect.value = portalErr.redirectRoute;
                portalRedirectLabel.value = portalErr.redirectLabel;
            } else {
                error.value = 'Usuário ou senha inválidos.';
            }
        } finally {
            submitting.value = false;
        }
    };

    const handlePasswordReset = async () => {
        resetError.value = null;
        resetSuccess.value = false;
        resetLoading.value = true;
        try {
            await ApiService.requestPasswordReset({ email: resetEmail.value });
            resetSuccess.value = true;
        } catch {
            resetError.value = 'Não foi possível encontrar um usuário com este e-mail.';
        } finally {
            resetLoading.value = false;
        }
    };

    const onResetDialogHide = () => {
        resetEmail.value = '';
        resetError.value = null;
        resetSuccess.value = false;
        resetLoading.value = false;
    };

    const alternatePortal =
        portal === 'vereador'
            ? {
                  label: 'Acesso Prefeitura',
                  route: '/login'
              }
            : {
                  label: 'Acesso Vereador',
                  route: '/login/vereador'
              };

    const perfisAceitos = PORTAL_AUTH[portal]?.perfis || [];

    return {
        route,
        username,
        password,
        error,
        portalRedirect,
        portalRedirectLabel,
        rememberMe,
        submitting,
        showResetPasswordDialog,
        resetEmail,
        resetSuccess,
        resetError,
        resetLoading,
        alternatePortal,
        perfisAceitos,
        handleLogin,
        handlePasswordReset,
        onResetDialogHide
    };
}
