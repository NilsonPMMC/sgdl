"""Testes dos relatórios gerenciais."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone

from core.models import Demanda, UnidadeAdministrativa
from reports.serializers import calcular_sla_demanda
from reports.services import agregar_funil_status, calcular_metricas_sla, GARGALO_ETAPA_HORAS, agregar_por_setor
from reports.views import BaseReportView

User = get_user_model()


class RelatorioSerializerTests(TestCase):
    def test_calcular_sla_atrasada(self):
        demanda = Demanda(
            status='EM_EXECUCAO',
            data_inicio_prazo=timezone.now() - timedelta(days=20),
            prazo_efetivo_dias=5,
            prazo_origem='SERVICO',
        )
        sla = calcular_sla_demanda(demanda)
        self.assertTrue(sla['is_atrasada'])
        self.assertGreater(sla['dias_pos_protocolo'], 0)

    def test_rascunho_excluido_do_base_report(self):
        gestor = User.objects.create_user(username='gestor_rel', password='x', perfil='GESTOR')
        Demanda.objects.create(titulo='Rasc', descricao='x', status='RASCUNHO', autor=gestor)
        Demanda.objects.create(titulo='Aberta', descricao='x', status='AGUARDANDO_PROTOCOLO', autor=gestor)

        req = RequestFactory().get('/api/reports/kpis/')
        req.user = gestor
        qs = BaseReportView().get_filtered_queryset(req)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().status, 'AGUARDANDO_PROTOCOLO')

    def test_metricas_sla_encerradas(self):
        gestor = User.objects.create_user(username='gestor_sla', password='x', perfil='GESTOR')
        inicio = timezone.now() - timedelta(days=10)
        Demanda.objects.create(
            titulo='Ok',
            descricao='x',
            status='FINALIZADO',
            autor=gestor,
            data_inicio_prazo=inicio,
            data_finalizacao=inicio + timedelta(days=3),
            prazo_efetivo_dias=5,
            prazo_origem='SERVICO',
        )
        qs = Demanda.objects.all()
        metricas = calcular_metricas_sla(qs)
        self.assertEqual(metricas['encerradas_com_sla'], 1)
        self.assertEqual(metricas['encerradas_no_prazo'], 1)
        self.assertEqual(metricas['pct_encerradas_no_sla'], 100.0)

    def test_gargalo_setor(self):
        gestor = User.objects.create_user(username='gestor_garg', password='x', perfil='GESTOR')
        unidade = UnidadeAdministrativa.objects.create(nome='Teste', sigla='TST', sinapse_orgao_id=1)
        Demanda.objects.create(
            titulo='Lenta',
            descricao='x',
            status='EM_EXECUCAO',
            autor=gestor,
            unidade_administrativa=unidade,
            data_entrada_etapa=timezone.now() - timedelta(hours=GARGALO_ETAPA_HORAS + 5),
            data_inicio_prazo=timezone.now() - timedelta(days=5),
            prazo_efetivo_dias=10,
            prazo_origem='SERVICO',
        )
        resultado = agregar_por_setor(Demanda.objects.all())
        self.assertEqual(len(resultado), 1)
        self.assertTrue(resultado[0]['gargalo'])

    def test_funil_retorna_estrutura(self):
        gestor = User.objects.create_user(username='gestor_funil', password='x', perfil='GESTOR')
        criacao = timezone.now() - timedelta(days=15)
        Demanda.objects.create(
            titulo='Fluxo',
            descricao='x',
            status='FINALIZADO',
            autor=gestor,
            data_criacao=criacao,
            data_inicio_prazo=criacao + timedelta(days=5),
            data_finalizacao=criacao + timedelta(days=12),
            prazo_efetivo_dias=20,
            prazo_origem='SERVICO',
        )
        funil = agregar_funil_status(Demanda.objects.all())
        self.assertEqual(len(funil), 3)
        self.assertTrue(any(f['amostras'] > 0 for f in funil))
