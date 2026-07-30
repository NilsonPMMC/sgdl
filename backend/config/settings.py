"""
Django settings for config project.
"""
from pathlib import Path
from dotenv import load_dotenv
import os
import dj_database_url
from datetime import timedelta

from celery.schedules import crontab

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

dotenv_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=dotenv_path)

# Quick-start development settings
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").lower()
DEBUG = os.environ.get("DEBUG", "False").lower() == "true"

def env_list(key, default=""):
    raw = os.environ.get(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if ENVIRONMENT in ("production", "prod"):
        raise RuntimeError("SECRET_KEY é obrigatória em produção.")
    SECRET_KEY = "local-dev-only-change-this-secret-key-with-50-plus-chars"

ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    "sgdl.mogidascruzes.sp.gov.br,localhost,127.0.0.1"
)

CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    "https://sgdl.mogidascruzes.sp.gov.br"
)

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'django_filters',
    'corsheaders',
    'core',
    'reports',
    'integrations',
]

AUTH_USER_MODEL = 'core.Usuario'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database Setup (Aceita DATABASE_URL ou as chaves separadas do .env)
DB_URL = os.environ.get('DATABASE_URL')
if DB_URL:
    DATABASES = {
        'default': dj_database_url.parse(DB_URL, conn_max_age=600)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.postgresql'),
            'NAME': os.environ.get('DB_NAME', 'sgdl_db'),
            'USER': os.environ.get('DB_USER', 'sgdl_user'),
            'PASSWORD': os.environ.get('DB_PASSWORD', 'senha_forte_aqui'),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
            'CONN_MAX_AGE': 600,
        }
    }

# --- Barramento Sinapse (multi-database, somente leitura via .using('sinapse')) ---
# Os models do Sinapse vivem em backend/integrations/models_sinapse.py com
# managed = False. Nenhuma migracao do SGDL roda contra este DB.
if os.environ.get('SINAPSE_DB_NAME'):
    DATABASES['sinapse'] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('SINAPSE_DB_NAME', ''),
        'USER': os.environ.get('SINAPSE_DB_USER', ''),
        'PASSWORD': os.environ.get('SINAPSE_DB_PASSWORD', ''),
        'HOST': os.environ.get('SINAPSE_DB_HOST', ''),
        'PORT': os.environ.get('SINAPSE_DB_PORT', '5432'),
        'CONN_MAX_AGE': 600,
        'OPTIONS': {
            'connect_timeout': 5,
        },
        'TEST': {
            # SGDL nao cria/destroi o DB do barramento em testes.
            'MIRROR': 'default',
        },
    }
    DATABASE_ROUTERS = ['integrations.db_routers.SinapseRouter']

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization (Ajustado para o Brasil - SLA e Gestão de Prazos)
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    "https://sgdl.mogidascruzes.sp.gov.br,http://localhost:5174"
)
CORS_ORIGIN_ALLOW_ALL = False

# Media
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Geocodificação (Nominatim / OpenStreetMap)
GEOCODING_USER_AGENT = os.environ.get(
    'GEOCODING_USER_AGENT',
    'SGDL-Gabinete/1.0 (comunicacao.gabinete@mogidascruzes.sp.gov.br)',
)
GEOCODING_TIMEOUT = int(os.environ.get('GEOCODING_TIMEOUT', '12'))
GEOCODING_CIDADE = os.environ.get('GEOCODING_CIDADE', 'Mogi das Cruzes')
GEOCODING_UF = os.environ.get('GEOCODING_UF', 'SP')
# Nominatim público: ~1 req/s; cache e poucas variantes evitam HTTP 429
GEOCODING_NOMINATIM_MIN_INTERVAL = float(
    os.environ.get('GEOCODING_NOMINATIM_MIN_INTERVAL', '1.1')
)
GEOCODING_CACHE_TTL = int(os.environ.get('GEOCODING_CACHE_TTL', '86400'))
GEOCODING_MAX_VARIANTES_VIA = int(os.environ.get('GEOCODING_MAX_VARIANTES_VIA', '2'))
GEOCODING_NOMINATIM_429_BACKOFF = int(os.environ.get('GEOCODING_NOMINATIM_429_BACKOFF', '90'))
GEOCODING_VIA_REFERENCIA_ENABLED = os.environ.get(
    'GEOCODING_VIA_REFERENCIA_ENABLED', 'True'
).lower() == 'true'
GEOCODING_VIA_REFERENCIA_AUTO_REGISTER = os.environ.get(
    'GEOCODING_VIA_REFERENCIA_AUTO_REGISTER', 'True'
).lower() == 'true'
GEOCODING_LLM_PARSING_ENABLED = os.environ.get(
    'GEOCODING_LLM_PARSING_ENABLED', 'True'
).lower() == 'true'
GEOCODING_BAIRRO_FUZZY_THRESHOLD = int(
    os.environ.get('GEOCODING_BAIRRO_FUZZY_THRESHOLD', '90')
)

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    )
}

# E-mail
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST')
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = os.environ.get('SMTP_USER')
EMAIL_HOST_PASSWORD = os.environ.get('SMTP_PASSWORD')
DEFAULT_FROM_EMAIL = 'comunicacao.gabinete@mogidascruzes.sp.gov.br'

FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5173')

# Segurança
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', str(not DEBUG)).lower() == 'true'
SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', str(not DEBUG)).lower() == 'true'
CSRF_COOKIE_SECURE = os.environ.get('CSRF_COOKIE_SECURE', str(not DEBUG)).lower() == 'true'
SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000' if not DEBUG else '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get('SECURE_HSTS_INCLUDE_SUBDOMAINS', 'True').lower() == 'true'
SECURE_HSTS_PRELOAD = os.environ.get('SECURE_HSTS_PRELOAD', 'True').lower() == 'true'

# Kernel AI compartilhado
AI_KERNEL_BASE_URL = os.environ.get("AI_KERNEL_BASE_URL", "http://localhost:8004")
AI_KERNEL_TIMEOUT_EMBEDDINGS = int(os.environ.get("AI_KERNEL_TIMEOUT_EMBEDDINGS", "10"))
AI_KERNEL_TIMEOUT_SIMILARITY = int(os.environ.get("AI_KERNEL_TIMEOUT_SIMILARITY", "10"))
AI_KERNEL_TIMEOUT_CHAT = int(os.environ.get("AI_KERNEL_TIMEOUT_CHAT", "30"))
AI_KERNEL_MAX_RETRIES = int(os.environ.get("AI_KERNEL_MAX_RETRIES", "2"))
AI_KERNEL_RETRY_BACKOFF_SECONDS = float(os.environ.get("AI_KERNEL_RETRY_BACKOFF_SECONDS", "0.5"))
# "gabinete" = payload {"texts": [...]} (Kernel SGDL/MOVA)
# "openai"   = payload {"input": ..., "model": ...} (OpenAI-compatible)
AI_KERNEL_EMBEDDING_PAYLOAD = os.environ.get("AI_KERNEL_EMBEDDING_PAYLOAD", "gabinete").lower()
AI_KERNEL_EMBEDDING_MODEL = os.environ.get("AI_KERNEL_EMBEDDING_MODEL", "mxbai-embed-large")

# LLM Groq (triagem semantica / extracao de entidades de demandas)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_BASE_URL = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1/chat/completions")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_TIMEOUT = int(os.environ.get("GROQ_TIMEOUT", "15"))
GROQ_TEMPERATURE = float(os.environ.get("GROQ_TEMPERATURE", "0.1"))

# Sinapse (barramento/interoperabilidade)
SINAPSE_DB_NAME = os.environ.get("SINAPSE_DB_NAME", "")
SINAPSE_DB_USER = os.environ.get("SINAPSE_DB_USER", "")
SINAPSE_DB_PASSWORD = os.environ.get("SINAPSE_DB_PASSWORD", "")
SINAPSE_DB_HOST = os.environ.get("SINAPSE_DB_HOST", "")
SINAPSE_DB_PORT = int(os.environ.get("SINAPSE_DB_PORT", "5432"))
SINAPSE_SERVICE_TABLE = os.environ.get("SINAPSE_SERVICE_TABLE", "catalog_servico")
SINAPSE_ALERT_UNMATCHED_THRESHOLD = int(os.environ.get("SINAPSE_ALERT_UNMATCHED_THRESHOLD", "200"))
SINAPSE_ALERT_DIVERGENT_THRESHOLD = int(os.environ.get("SINAPSE_ALERT_DIVERGENT_THRESHOLD", "20"))
SINAPSE_ALERT_EMAIL_RECIPIENTS = env_list("SINAPSE_ALERT_EMAIL_RECIPIENTS", "")
SINAPSE_ALERT_WEBHOOK_URL = os.environ.get("SINAPSE_ALERT_WEBHOOK_URL", "")
SINAPSE_ALERT_WEBHOOK_TIMEOUT = int(os.environ.get("SINAPSE_ALERT_WEBHOOK_TIMEOUT", "10"))
# Triagem copiloto / debug: loga ranking no logger; mescla busca lexical em titulo/texto_limpo_rag
SINAPSE_TRIAGEM_LOG = os.environ.get("SINAPSE_TRIAGEM_LOG", "False").lower() == "true"
SINAPSE_TRIAGEM_LEXICAL_MERGE = os.environ.get("SINAPSE_TRIAGEM_LEXICAL_MERGE", "True").lower() == "true"

# Tendências (solicitações fora da carta Sinapse) — braço interno + copiloto
COPILOTO_TENDENCIAS_ENABLED = os.environ.get("COPILOTO_TENDENCIAS_ENABLED", "True").lower() == "true"
# FAQ de orientação (fora da competência) — desativada por padrão; pedidos seguem carta ou tendência.
COPILOTO_FAQ_ENABLED = os.environ.get("COPILOTO_FAQ_ENABLED", "False").lower() == "true"
TENDENCIA_SIMILARITY_THRESHOLD = float(os.environ.get("TENDENCIA_SIMILARITY_THRESHOLD", "0.85"))
COPILOTO_TRIAGEM_SCORE_LIMIAR = float(os.environ.get("COPILOTO_TRIAGEM_SCORE_LIMIAR", "0.45"))
# Corpus legado (aprendizado — não importa Demandas; JSON gerado por analisar_corpus_legado)
CORPUS_LEGADO_ENABLED = os.environ.get("CORPUS_LEGADO_ENABLED", "True").lower() == "true"
CORPUS_LEGADO_HINTS_COPILOTO_ENABLED = (
    os.environ.get("CORPUS_LEGADO_HINTS_COPILOTO_ENABLED", "True").lower() == "true"
)
CORPUS_LEGADO_CSV_PATH = os.environ.get(
    "CORPUS_LEGADO_CSV_PATH", "docs/bd-legado-demandas-vereadores.csv"
)
CORPUS_LEGADO_JSON_PATH = os.environ.get(
    "CORPUS_LEGADO_JSON_PATH", "docs/insights/corpus-legado.json"
)
CORPUS_LEGADO_DEPARA_PATH = os.environ.get(
    "CORPUS_LEGADO_DEPARA_PATH", "docs/insights/depara-legado-sinapse.json"
)
# Score mínimo na carta Sinapse para priorizar escolha de serviço (abaixo disso → tendência).
COPILOTO_CARTA_SCORE_MINIMO = float(os.environ.get("COPILOTO_CARTA_SCORE_MINIMO", "0.6666"))
# Limiar mais baixo ao listar serviços por domínio operacional (ex.: mobilidade).
COPILOTO_CARTA_SCORE_DOMINIO = float(os.environ.get("COPILOTO_CARTA_SCORE_DOMINIO", "0.40"))
# Trilha A′ — serviço Sinapse «Atendimento ao Cidadão (Ouvidoria)» (O1).
COPILOTO_OUVIDORIA_SINAPSE_SERVICO_ID = int(
    os.environ.get("COPILOTO_OUVIDORIA_SINAPSE_SERVICO_ID", "13")
)

# Clusterização (Super Ordem de Serviço) — semântica 1024d + raio geográfico
CLUSTER_ENABLED = os.environ.get("CLUSTER_ENABLED", "True").lower() == "true"
CLUSTER_SEMANTIC_THRESHOLD = float(os.environ.get("CLUSTER_SEMANTIC_THRESHOLD", "0.70"))
CLUSTER_RADIUS_METERS = float(os.environ.get("CLUSTER_RADIUS_METERS", "300"))
# Dias em que um cluster aberto ainda aceita novas demandas semelhantes (0 = sem limite).
CLUSTER_JANELA_AGREGACAO_DIAS = int(os.environ.get("CLUSTER_JANELA_AGREGACAO_DIAS", "90"))
# Janela (segundos) para corrigir ou desfazer tramitação/despacho após registro.
DESPACHO_JANELA_EDICAO_SEGUNDOS = int(os.environ.get("DESPACHO_JANELA_EDICAO_SEGUNDOS", "60"))
CLUSTER_REQUER_MESMO_SERVICO = os.environ.get("CLUSTER_REQUER_MESMO_SERVICO", "True").lower() == "true"
# Aguarda rascunhos / embeddings pendentes do mesmo serviço antes de despacho solo automático.
CLUSTER_FORMACAO_GRACE_MINUTES = int(os.environ.get("CLUSTER_FORMACAO_GRACE_MINUTES", "20"))

# Base de Serviços Otimizada — substitui consultas diretas ao Sinapse
USAR_BASE_SERVICOS_OTIMIZADA = os.environ.get("USAR_BASE_SERVICOS_OTIMIZADA", "True").lower() == "true"
# Fallback automático para Sinapse se base otimizada falhar
BASE_OTIMIZADA_FALLBACK_ENABLED = os.environ.get("BASE_OTIMIZADA_FALLBACK_ENABLED", "True").lower() == "true"

# JWT Options
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME_REMEMBER_ME': timedelta(days=30),
}

# Celery — broker/fila exclusivos do SGDL (Redis DB 15 por padrão; não compartilhar com SIGA/CIPTEA)
CELERY_ENABLED = os.environ.get("CELERY_ENABLED", "False").lower() == "true"
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://127.0.0.1:6379/15")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_DEFAULT_QUEUE = os.environ.get("CELERY_TASK_DEFAULT_QUEUE", "sgdl_default")
CELERY_TASK_ROUTES = {
    "sgdl.*": {"queue": "sgdl_default"},
}
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_WORKER_SEND_TASK_EVENTS = False
CELERY_WORKER_DISABLE_GOSSIP = True
CELERY_WORKER_DISABLE_MINGLE = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
# Beat SLA: diário 07:00 (America/Sao_Paulo) — substitui cron manual quando Celery ativo
CELERY_BEAT_SCHEDULE = {
    "sgdl-verificar-atrasos-diario": {
        "task": "sgdl.verificar_atrasos",
        "schedule": crontab(hour=7, minute=0),
        "options": {"queue": "sgdl_default"},
    },
}