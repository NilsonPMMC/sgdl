from django.test import TestCase
from django.utils import timezone

from core.models import Demanda, Notificacao, Usuario
from core.services.atraso_demanda_service import AtrasoDemandaService


class AtrasoDemandaServiceTests(TestCase):
    def test_demanda_vencida_gera_notificacao(self):
        gestor = Usuario.objects.create_user(
            username="gestor_atraso",
            password="x",
            perfil="GESTOR",
        )
        autor = Usuario.objects.create_user(
            username="ver_atraso",
            password="x",
            perfil="VEREADOR",
        )
        demanda = Demanda.objects.create(
            titulo="Teste atraso",
            descricao="x",
            status="EM_EXECUCAO",
            autor=autor,
            data_inicio_prazo=timezone.now() - timezone.timedelta(days=40),
            prazo_efetivo_dias=10,
            prazo_origem="PADRAO",
            notificacao_atraso_enviada=False,
        )

        resultado = AtrasoDemandaService().executar()

        self.assertEqual(resultado.demandas_atrasadas, 1)
        self.assertGreaterEqual(resultado.notificacoes_criadas, 1)
        demanda.refresh_from_db()
        self.assertTrue(demanda.notificacao_atraso_enviada)
        self.assertTrue(
            Notificacao.objects.filter(destinatario=gestor, tipo="ATRASO").exists()
        )
