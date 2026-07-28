"""Testes de alerta de duplicidade do Copiloto."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Demanda
from core.services.copiloto_duplicidade_service import (
    _locais_compatíveis,
    alertas_duplicidade_para_demanda,
    buscar_alertas_duplicidade,
    resumir_alertas_duplicidade,
)
from core.services.oficio_texto import montar_texto_oficio

Usuario = get_user_model()

SERVICO_BURACO = 80


@patch("integrations.sinapse_catalog.servico_requer_localizacao", return_value=True)
class CopilotoDuplicidadeTests(TestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user(
            username="dup_user",
            password="x",
            perfil="VEREADOR",
        )

    def _oficio(self, *, titulo: str, relato: str, endereco: str = "") -> str:
        return montar_texto_oficio(
            titulo=titulo,
            relato=relato,
            endereco_formatado=endereco,
            servico_nome="Serviço teste",
            orgao_nome="Órgão teste",
            autor_nome="Vereador Teste",
            autor_cargo="Vereador",
        )

    def test_locais_compatíveis_dentro_do_raio(self, _mock_loc):
        ok = _locais_compatíveis(
            latitude_novo=-23.5505,
            longitude_novo=-46.6333,
            bairro_novo="Centro",
            latitude_existente=-23.5506,
            longitude_existente=-46.6334,
            bairro_existente="Centro",
            sinapse_servico_id=SERVICO_BURACO,
        )
        self.assertTrue(ok)

    def test_locais_incompatíveis_fora_do_raio(self, _mock_loc):
        ok = _locais_compatíveis(
            latitude_novo=-23.5505,
            longitude_novo=-46.6333,
            bairro_novo="Centro",
            latitude_existente=-23.6000,
            longitude_existente=-46.7000,
            bairro_existente="Centro",
            sinapse_servico_id=SERVICO_BURACO,
        )
        self.assertFalse(ok)

    def test_mesmo_servico_locais_diferentes_nao_alertam(self, _mock_loc):
        desc_a = self._oficio(
            titulo="Reparo em buracos na via",
            relato="buraco na Rua A",
            endereco="Rua A, 10 — Bairro Norte",
        )
        desc_b = self._oficio(
            titulo="Tapa buraco na via",
            relato="buraco na Rua B distante",
            endereco="Rua B, 200 — Bairro Sul",
        )
        Demanda.objects.create(
            titulo="Reparo em buracos na via",
            descricao=desc_a,
            autor=self.user,
            status="EM_EXECUCAO",
            sinapse_servico_id=SERVICO_BURACO,
            sinapse_orgao_id=1,
            latitude=-23.5505,
            longitude=-46.6333,
            bairro="Norte",
        )
        d_nova = Demanda.objects.create(
            titulo="Tapa buraco na via",
            descricao=desc_b,
            autor=self.user,
            status="RASCUNHO",
            sinapse_servico_id=SERVICO_BURACO,
            sinapse_orgao_id=1,
            latitude=-23.6000,
            longitude=-46.7000,
            bairro="Sul",
        )
        alertas = buscar_alertas_duplicidade(
            self.user,
            titulo=d_nova.titulo,
            descricao=d_nova.descricao,
            sinapse_servico_id=SERVICO_BURACO,
            latitude=-23.6000,
            longitude=-46.7000,
            bairro="Sul",
            excluir_demanda_id=d_nova.id,
        )
        self.assertEqual(alertas, [])

    def test_mesmo_servico_mesmo_local_alertam(self, _mock_loc):
        desc = self._oficio(
            titulo="Poda de árvore",
            relato="poda de arvore na Rua João Ribeiro",
            endereco="Rua João Ribeiro, 114 — Bairro Vila Suissa",
        )
        existente = Demanda.objects.create(
            titulo="Poda de árvore",
            descricao=desc,
            autor=self.user,
            status="RASCUNHO",
            sinapse_servico_id=100,
            sinapse_orgao_id=1,
            latitude=-23.5505,
            longitude=-46.6333,
            bairro="Vila Suissa",
        )
        d_nova = Demanda.objects.create(
            titulo="Poda de árvore",
            descricao=desc,
            autor=self.user,
            status="RASCUNHO",
            sinapse_servico_id=100,
            sinapse_orgao_id=1,
            latitude=-23.5506,
            longitude=-46.6334,
            bairro="Vila Suissa",
        )
        alertas = buscar_alertas_duplicidade(
            self.user,
            titulo=d_nova.titulo,
            descricao=d_nova.descricao,
            sinapse_servico_id=100,
            latitude=-23.5506,
            longitude=-46.6334,
            bairro="Vila Suissa",
            excluir_demanda_id=d_nova.id,
        )
        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0]["demanda_id"], existente.id)

    def test_servicos_diferentes_nao_alertam(self, _mock_loc):
        desc_upa = self._oficio(
            titulo="Denúncia de atendimento na UPA Jundiapeba",
            relato="quero registrar denuncia sobre atendimento da UPA Jundiapeba",
        )
        desc_buraco = self._oficio(
            titulo="Reparo em buracos na via",
            relato="solicito limpeza de rua",
            endereco="Rua João Ribeiro, 114 — Bairro Vila Suissa",
        )
        Demanda.objects.create(
            titulo="Reparo em buracos na via",
            descricao=desc_buraco,
            autor=self.user,
            status="RASCUNHO",
            sinapse_servico_id=SERVICO_BURACO,
            sinapse_orgao_id=1,
            latitude=-23.5505,
            longitude=-46.6333,
            bairro="Vila Suissa",
        )
        d_nova = Demanda.objects.create(
            titulo="Denúncia de atendimento na UPA Jundiapeba",
            descricao=desc_upa,
            autor=self.user,
            status="RASCUNHO",
            sinapse_servico_id=13,
            sinapse_orgao_id=1,
            latitude=-23.5505,
            longitude=-46.6333,
            bairro="Vila Suissa",
        )
        alertas = buscar_alertas_duplicidade(
            self.user,
            titulo=d_nova.titulo,
            descricao=d_nova.descricao,
            sinapse_servico_id=13,
            latitude=-23.5505,
            longitude=-46.6333,
            bairro="Vila Suissa",
            excluir_demanda_id=d_nova.id,
        )
        self.assertEqual(alertas, [])

    def test_buscar_alertas_exclui_propria_demanda(self, _mock_loc):
        desc = self._oficio(
            titulo="Poda de árvore",
            relato="poda de arvore na rua A",
        )
        d = Demanda.objects.create(
            titulo="Poda de árvore",
            descricao=desc,
            autor=self.user,
            status="RASCUNHO",
            sinapse_servico_id=100,
            sinapse_orgao_id=1,
            latitude=-23.5505,
            longitude=-46.6333,
            bairro="Centro",
        )
        alertas = buscar_alertas_duplicidade(
            self.user,
            titulo=d.titulo,
            descricao=d.descricao,
            sinapse_servico_id=100,
            latitude=-23.5505,
            longitude=-46.6333,
            bairro="Centro",
            excluir_demanda_id=d.id,
        )
        self.assertEqual(alertas, [])

    def test_nao_compara_finalizado(self, _mock_loc):
        desc = self._oficio(titulo="Poda de árvore", relato="poda de arvore na rua A")
        Demanda.objects.create(
            titulo="Poda de árvore",
            descricao=desc,
            autor=self.user,
            status="FINALIZADO",
            sinapse_servico_id=100,
            sinapse_orgao_id=1,
            latitude=-23.5505,
            longitude=-46.6333,
            bairro="Centro",
        )
        d_nova = Demanda.objects.create(
            titulo="Poda de árvore",
            descricao=desc,
            autor=self.user,
            status="RASCUNHO",
            sinapse_servico_id=100,
            sinapse_orgao_id=1,
            latitude=-23.5505,
            longitude=-46.6333,
            bairro="Centro",
        )
        alertas = buscar_alertas_duplicidade(
            self.user,
            titulo=d_nova.titulo,
            descricao=d_nova.descricao,
            sinapse_servico_id=100,
            latitude=-23.5505,
            longitude=-46.6333,
            bairro="Centro",
            excluir_demanda_id=d_nova.id,
        )
        self.assertEqual(alertas, [])

    def test_nivel_em_tramite_aguardando_protocolo(self, _mock_loc):
        desc = self._oficio(titulo="Poda de árvore", relato="poda de arvore na rua A")
        existente = Demanda.objects.create(
            titulo="Poda de árvore",
            descricao=desc,
            autor=self.user,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_servico_id=100,
            sinapse_orgao_id=1,
            latitude=-23.5505,
            longitude=-46.6333,
            bairro="Centro",
        )
        d_nova = Demanda.objects.create(
            titulo="Poda de árvore",
            descricao=desc,
            autor=self.user,
            status="RASCUNHO",
            sinapse_servico_id=100,
            sinapse_orgao_id=1,
            latitude=-23.5506,
            longitude=-46.6334,
            bairro="Centro",
        )
        alertas = buscar_alertas_duplicidade(
            self.user,
            titulo=d_nova.titulo,
            descricao=d_nova.descricao,
            sinapse_servico_id=100,
            latitude=-23.5506,
            longitude=-46.6334,
            bairro="Centro",
            excluir_demanda_id=d_nova.id,
        )
        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0]["demanda_id"], existente.id)
        self.assertEqual(alertas[0]["nivel"], "em_tramite")
        self.assertEqual(alertas[0]["gravidade"], "alta")

    def test_nivel_rascunho(self, _mock_loc):
        desc = self._oficio(titulo="Poda de árvore", relato="poda de arvore na rua A")
        existente = Demanda.objects.create(
            titulo="Poda de árvore",
            descricao=desc,
            autor=self.user,
            status="RASCUNHO",
            sinapse_servico_id=100,
            sinapse_orgao_id=1,
            latitude=-23.5505,
            longitude=-46.6333,
            bairro="Centro",
        )
        d_nova = Demanda.objects.create(
            titulo="Poda de árvore",
            descricao=desc,
            autor=self.user,
            status="RASCUNHO",
            sinapse_servico_id=100,
            sinapse_orgao_id=1,
            latitude=-23.5506,
            longitude=-46.6334,
            bairro="Centro",
        )
        alertas = buscar_alertas_duplicidade(
            self.user,
            titulo=d_nova.titulo,
            descricao=d_nova.descricao,
            sinapse_servico_id=100,
            latitude=-23.5506,
            longitude=-46.6334,
            bairro="Centro",
            excluir_demanda_id=d_nova.id,
        )
        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0]["demanda_id"], existente.id)
        self.assertEqual(alertas[0]["nivel"], "rascunho")
        self.assertEqual(alertas[0]["gravidade"], "media")

    def test_resumir_sugerir_nao_enviar(self, _mock_loc):
        alertas = [
            {
                "demanda_id": 1,
                "status": "AGUARDANDO_PROTOCOLO",
                "status_label": "Aguardando protocolo",
                "nivel": "em_tramite",
            },
        ]
        resumo = resumir_alertas_duplicidade(alertas)
        self.assertTrue(resumo["sugerir_nao_enviar"])
        self.assertTrue(resumo["tem_em_tramite"])

    def test_alertas_para_envio_oficial(self, _mock_loc):
        desc = self._oficio(titulo="Poda de árvore", relato="poda de arvore na rua A")
        existente = Demanda.objects.create(
            titulo="Poda de árvore",
            descricao=desc,
            autor=self.user,
            status="EM_EXECUCAO",
            sinapse_servico_id=100,
            sinapse_orgao_id=1,
            latitude=-23.5505,
            longitude=-46.6333,
            bairro="Centro",
        )
        d_envio = Demanda.objects.create(
            titulo="Poda de árvore",
            descricao=desc,
            autor=self.user,
            status="RASCUNHO",
            sinapse_servico_id=100,
            sinapse_orgao_id=1,
            latitude=-23.5506,
            longitude=-46.6334,
            bairro="Centro",
        )
        pacote = alertas_duplicidade_para_demanda(d_envio, self.user)
        self.assertTrue(pacote["duplicidade_resumo"]["sugerir_nao_enviar"])
        self.assertEqual(pacote["alertas_duplicidade"][0]["demanda_id"], existente.id)

    def test_sem_servico_sinapse_nao_alertam(self, _mock_loc):
        desc = self._oficio(titulo="Pedido genérico", relato="algo na rua")
        Demanda.objects.create(
            titulo="Pedido genérico",
            descricao=desc,
            autor=self.user,
            status="RASCUNHO",
            latitude=-23.5505,
            longitude=-46.6333,
            bairro="Centro",
        )
        alertas = buscar_alertas_duplicidade(
            self.user,
            titulo="Pedido genérico",
            descricao=desc,
            latitude=-23.5505,
            longitude=-46.6333,
            bairro="Centro",
        )
        self.assertEqual(alertas, [])
