"""Testes do serviço de mapa operacional (E3)."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone

from core.models import Demanda
from core.services.mapa_demanda_service import agregar_espacial_sazonal, filtrar_demandas_mapa

User = get_user_model()


class MapaDemandaServiceTests(TestCase):
    def setUp(self):
        self.gestor = User.objects.create_user(
            username='gestor_mapa',
            password='test',
            perfil='GESTOR',
        )
        self.factory = RequestFactory()
        agora = timezone.now()
        Demanda.objects.create(
            titulo='Buraco rua A',
            descricao='Teste',
            status='EM_EXECUCAO',
            latitude=-23.52,
            longitude=-46.18,
            bairro='Centro',
            sinapse_servico_id=10,
            data_criacao=agora - timedelta(days=10),
        )
        Demanda.objects.create(
            titulo='Buraco rua B',
            descricao='Teste',
            status='EM_EXECUCAO',
            latitude=-23.521,
            longitude=-46.181,
            bairro='Centro',
            sinapse_servico_id=10,
            data_criacao=agora - timedelta(days=5),
        )
        Demanda.objects.create(
            titulo='Sem geo',
            descricao='Teste',
            status='EM_EXECUCAO',
            bairro='Jardim',
        )

    def _request(self, **params):
        req = self.factory.get('/api/demandas/locations/', params)
        req.user = self.gestor
        return req

    def test_filtrar_apenas_com_coordenadas(self):
        qs = filtrar_demandas_mapa(self._request())
        self.assertEqual(qs.count(), 2)

    def test_agregacao_bairro_e_mes(self):
        qs = filtrar_demandas_mapa(self._request())
        data = agregar_espacial_sazonal(qs)
        self.assertEqual(data['total_geolocalizadas'], 2)
        self.assertTrue(any(b['bairro'] == 'Centro' for b in data['por_bairro']))
        self.assertTrue(len(data['por_mes']) >= 1)
        self.assertTrue(len(data['hotspots']) >= 1)
