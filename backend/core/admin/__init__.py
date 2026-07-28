"""
Django Admin do SGDL — pacote modular.

Seções principais (registrations.py):
  • Operação — demandas, tramitações, clusters, notificações
  • Copiloto — sessões de chat, FAQ, tendências
  • Carta — base otimizada, fluxo protocolo, assinaturas
  • Usuários — perfis SGDL e unidades administrativas
  • Configuração — ofício institucional

Complementares (complementares.py):
  • SLA carta, assuntos, de-para RM, encerramento legislativo
  • Metadados ricos, vínculos UA, anexos de chat, regex FAQ avulsos
"""

from .site import configurar_admin_site

configurar_admin_site()

from . import complementares  # noqa: F401, E402
from . import registrations  # noqa: F401, E402
