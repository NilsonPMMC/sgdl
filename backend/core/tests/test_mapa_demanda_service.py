"""Testes do serviço de mapa operacional (E3)."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone

from core.models import Demanda
from core.services.mapa_demanda_service import (
    agregar_espacial_sazonal,
    filtrar_demandas_mapa,
    serializar_locations,
)

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

    def test_filtrar_apenas_com_coordenadas_ou_endereco_completo(self):
        qs = filtrar_demandas_mapa(self._request())
        self.assertEqual(qs.count(), 2)

    def test_exclui_demanda_sem_coords_e_sem_endereco_geocodificavel(self):
        locs = serializar_locations(filtrar_demandas_mapa(self._request()))
        titulos = {loc['titulo'] for loc in locs}
        self.assertNotIn('Sem geo', titulos)
        self.assertEqual(len(locs), 2)

    def test_agregacao_bairro_e_mes(self):
        qs = filtrar_demandas_mapa(self._request())
        data = agregar_espacial_sazonal(qs)
        self.assertEqual(data['total_geolocalizadas'], 2)
        self.assertTrue(any(b['bairro'] == 'Centro' for b in data['por_bairro']))
        self.assertTrue(len(data['por_mes']) >= 1)
        self.assertTrue(len(data['hotspots']) >= 1)

    def test_agregacao_total_igual_serializar_locations(self):
        qs = filtrar_demandas_mapa(self._request())
        locs = serializar_locations(qs)
        data = agregar_espacial_sazonal(qs)
        self.assertEqual(data['total_geolocalizadas'], len(locs))
        self.assertEqual(sum(b['total'] for b in data['por_bairro']), len(locs))

    @patch('core.services.geocoding_service.GeocodingService')
    def test_endereco_sem_geocode_nao_entra_na_agregacao(self, mock_geo_cls):
        Demanda.objects.create(
            titulo='Endereco sem geo',
            descricao='Teste',
            status='EM_EXECUCAO',
            logradouro='Rua Inexistente',
            bairro='Centro',
            sinapse_servico_id=20,
        )
        mock_geo_cls.return_value.resolver_endereco_geocode.return_value = {
            'latitude': None,
            'longitude': None,
            'latitude_bruta': None,
            'longitude_bruta': None,
            'fonte': 'indisponivel',
        }
        qs = filtrar_demandas_mapa(self._request())
        self.assertEqual(qs.count(), 3)
        locs = serializar_locations(qs)
        data = agregar_espacial_sazonal(qs)
        self.assertEqual(len(locs), 2)
        self.assertEqual(data['total_geolocalizadas'], 2)
        self.assertNotIn('Endereco sem geo', {loc['titulo'] for loc in locs})

    def test_camara_ve_rascunho_geolocalizado_proprio(self):
        camara = User.objects.create_user(
            username='camara_mapa',
            password='test',
            perfil='CAMARA',
        )
        Demanda.objects.create(
            titulo='Indicação rascunho',
            descricao='Teste',
            status='RASCUNHO',
            latitude=-23.522,
            longitude=-46.182,
            bairro='Vila',
            autor=camara,
        )
        req = self.factory.get('/api/demandas/locations/')
        req.user = camara
        qs = filtrar_demandas_mapa(req)
        self.assertEqual(qs.count(), 1)

    def test_filtrar_consulta_atrasadas_hjul19(self):
        agora = timezone.now()
        atrasada = Demanda.objects.create(
            titulo='Demanda atrasada mapa',
            descricao='Teste',
            status='PROTOCOLADO',
            latitude=-23.519,
            longitude=-46.179,
            bairro='Centro',
            data_inicio_prazo=agora - timedelta(days=20),
            prazo_efetivo_dias=5,
        )
        Demanda.objects.create(
            titulo='Demanda no prazo mapa',
            descricao='Teste',
            status='PROTOCOLADO',
            latitude=-23.518,
            longitude=-46.178,
            bairro='Centro',
            data_inicio_prazo=agora - timedelta(days=2),
            prazo_efetivo_dias=30,
        )
        qs = filtrar_demandas_mapa(self._request(consulta='atrasadas'))
        ids = set(qs.values_list('pk', flat=True))
        self.assertIn(atrasada.pk, ids)
        self.assertEqual(len(ids), 1)
        self.assertEqual(qs.first().status, 'RASCUNHO')

    @patch('core.services.geocoding_service.GeocodingService')
    def test_indicacao_geocodifica_automaticamente_com_logradouro_e_bairro(self, mock_geo_cls):
        camara = User.objects.create_user(
            username='camara_geo',
            password='test',
            perfil='CAMARA',
        )
        demanda = Demanda.objects.create(
            titulo='Indicação com endereço',
            descricao='Teste',
            status='RASCUNHO',
            tipo_legislativo=Demanda.TIPO_LEGISLATIVO_INDICACAO,
            logradouro='Rua das Flores',
            bairro='Centro',
            autor=camara,
        )
        mock_geo_cls.return_value.resolver_endereco_geocode.return_value = {
            'latitude': -23.523,
            'longitude': -46.19,
            'logradouro': 'Rua das Flores',
            'bairro': 'Centro',
            'cep': None,
            'fonte': 'logradouro',
        }

        req = self.factory.get('/api/demandas/locations/')
        req.user = camara
        locs = serializar_locations(filtrar_demandas_mapa(req))

        self.assertEqual(len(locs), 1)
        self.assertAlmostEqual(locs[0]['lat'], -23.523, places=3)
        demanda.refresh_from_db()
        self.assertIsNotNone(demanda.latitude)
        self.assertIsNotNone(demanda.longitude)

    @patch('core.services.geocoding_service.GeocodingService')
    def test_indicacao_sem_geocode_nao_aparece_no_mapa(self, mock_geo_cls):
        camara = User.objects.create_user(
            username='camara_sem_geo',
            password='test',
            perfil='CAMARA',
        )
        Demanda.objects.create(
            titulo='Indicação endereço inválido',
            descricao='Teste',
            status='RASCUNHO',
            tipo_legislativo=Demanda.TIPO_LEGISLATIVO_INDICACAO,
            logradouro='Rua Inexistente',
            bairro='Centro',
            autor=camara,
        )
        mock_geo_cls.return_value.resolver_endereco_geocode.return_value = {
            'latitude': None,
            'longitude': None,
            'latitude_bruta': None,
            'longitude_bruta': None,
            'fonte': 'indisponivel',
        }

        req = self.factory.get('/api/demandas/locations/')
        req.user = camara
        locs = serializar_locations(filtrar_demandas_mapa(req))
        self.assertEqual(locs, [])
