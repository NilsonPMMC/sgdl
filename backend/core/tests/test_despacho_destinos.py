"""Testes de parse de destinos no despacho multi-secretaria (B5)."""

import importlib.util

from django.test import TestCase

from core.models import Demanda, Usuario
from core.models_unidade_administrativa import UnidadeAdministrativa
from core.services.demanda_despacho_destinos import (
    expandir_pernas_destinos,
    normalizar_destinos_multi_orgao,
    parse_destinos_despacho,
    resolve_destinos_despacho,
)
from core.services.demanda_despacho_service import DemandaDespachoService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class ParseDestinosDespachoTests(TestCase):
    def test_legado_secretaria_unica(self):
        destinos = parse_destinos_despacho({"secretaria_id": "42", "unidade_administrativa_id": "7"})
        self.assertEqual(len(destinos), 1)
        self.assertEqual(destinos[0]["secretaria_id"], 42)
        self.assertEqual(destinos[0]["unidade_administrativa_id"], 7)

    def test_lista_destinos(self):
        payload = {
            "destinos": [
                {"secretaria_id": 888010},
                {"secretaria_id": 888020, "unidade_administrativa_id": 3},
            ]
        }
        destinos = parse_destinos_despacho(payload)
        self.assertEqual(len(destinos), 2)
        self.assertEqual(destinos[1]["unidade_administrativa_id"], 3)

    def test_json_string_destinos(self):
        destinos = parse_destinos_despacho({"destinos": '[{"secretaria_id": 888005}]'})
        self.assertEqual(destinos[0]["secretaria_id"], 888005)

    def test_rejeita_secretaria_duplicada_sem_setor(self):
        with self.assertRaisesMessage(ValueError, "Não repita"):
            parse_destinos_despacho({"destinos": [{"secretaria_id": 1}, {"secretaria_id": 1}]})

    def test_multi_setor_mesmo_orgao(self):
        destinos = parse_destinos_despacho(
            {
                "destinos": [
                    {
                        "secretaria_id": 10,
                        "unidade_administrativa_ids": [3, 4, 5],
                    }
                ]
            }
        )
        self.assertEqual(len(destinos), 3)
        self.assertEqual({d["secretaria_id"] for d in destinos}, {10})
        self.assertEqual(
            sorted(d["unidade_administrativa_id"] for d in destinos), [3, 4, 5]
        )

    def test_pernas_planas_mesmo_orgao(self):
        destinos = parse_destinos_despacho(
            {
                "destinos": [
                    {"secretaria_id": 10, "unidade_administrativa_id": 1},
                    {"secretaria_id": 10, "unidade_administrativa_id": 2},
                ]
            }
        )
        self.assertEqual(len(destinos), 2)

    def test_rejeita_mais_de_cinco_orgaos(self):
        raw = [{"secretaria_id": i} for i in range(1, 7)]
        with self.assertRaisesMessage(ValueError, "Máximo de 5"):
            parse_destinos_despacho({"destinos": raw})

    def test_sem_destino(self):
        with self.assertRaisesMessage(ValueError, "secretaria_id ou destinos"):
            parse_destinos_despacho({})


class ValidarSetoresObrigatoriosTests(TestCase):
    def test_rejeita_orgao_com_setores_sem_unidade(self):
        UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=49,
            nome="Gabinete",
            sigla="GAB",
            ativo=True,
        )
        with self.assertRaisesMessage(ValueError, "Selecione ao menos um setor"):
            parse_destinos_despacho({"destinos": [{"secretaria_id": 49}]})

    def test_aceita_orgao_com_setores_e_unidade(self):
        ua = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=49,
            nome="Gabinete",
            sigla="GAB",
            ativo=True,
        )
        destinos = parse_destinos_despacho(
            {"destinos": [{"secretaria_id": 49, "unidade_administrativa_id": ua.pk}]}
        )
        self.assertEqual(destinos[0]["unidade_administrativa_id"], ua.pk)


class NormalizarDestinosMultiOrgaoTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_norm_dest", password="x", perfil="VEREADOR"
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_norm", password="x", perfil="PROTOCOLO"
        )

    def _demanda(self):
        return Demanda.objects.create(
            titulo="Buraco",
            descricao="x",
            autor=self.vereador,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            protocolo_legislativo="PL-NORM-001",
        )

    def test_apenas_orgao_integrado_mantem_competencia_carta(self):
        demanda = self._demanda()
        plano = normalizar_destinos_multi_orgao(
            demanda, [{"secretaria_id": SINAPSE_ORGAO_B}]
        )
        self.assertEqual(plano["orgao_competente_id"], SINAPSE_ORGAO_A)
        self.assertEqual(plano["orgaos_integrados_ids"], [SINAPSE_ORGAO_B])
        self.assertEqual(plano["destinos"][0]["secretaria_id"], SINAPSE_ORGAO_A)
        self.assertEqual(plano["destinos"][1]["secretaria_id"], SINAPSE_ORGAO_B)

    def test_ordem_selecao_nao_altera_competencia(self):
        demanda = self._demanda()
        plano = normalizar_destinos_multi_orgao(
            demanda,
            [
                {"secretaria_id": SINAPSE_ORGAO_B},
                {"secretaria_id": SINAPSE_ORGAO_A},
            ],
        )
        self.assertEqual(plano["destinos"][0]["secretaria_id"], SINAPSE_ORGAO_A)
        self.assertEqual(plano["destinos"][1]["secretaria_id"], SINAPSE_ORGAO_B)

    def test_resolve_sem_selecao_usa_orgao_carta(self):
        demanda = self._demanda()
        destinos = resolve_destinos_despacho(demanda, {})
        self.assertEqual(
            destinos,
            [{"secretaria_id": SINAPSE_ORGAO_A, "unidade_administrativa_id": None}],
        )

    def test_rejeita_muitas_pernas(self):
        raw = [
            {
                "secretaria_id": 1,
                "unidade_administrativa_ids": list(range(1, 32)),
            }
        ]
        with self.assertRaisesMessage(ValueError, "pernas"):
            parse_destinos_despacho({"destinos": raw})

    def test_normalizar_multi_setor_competente(self):
        demanda = self._demanda()
        plano = normalizar_destinos_multi_orgao(
            demanda,
            [{"secretaria_id": SINAPSE_ORGAO_A, "unidade_administrativa_ids": [101, 102]}],
        )
        self.assertEqual(plano["total_pernas"], 2)
        self.assertEqual(len(plano["destinos"]), 1)
        self.assertEqual(plano["destinos"][0]["unidade_administrativa_ids"], [101, 102])

    def test_rejeita_muitas_pernas(self):
        raw = [
            {
                "secretaria_id": 1,
                "unidade_administrativa_ids": list(range(1, 32)),
            }
        ]
        with self.assertRaisesMessage(ValueError, "pernas"):
            parse_destinos_despacho({"destinos": raw})

    def test_normalizar_multi_setor_competente(self):
        demanda = self._demanda()
        plano = normalizar_destinos_multi_orgao(
            demanda,
            [{"secretaria_id": SINAPSE_ORGAO_A, "unidade_administrativa_ids": [101, 102]}],
        )
        self.assertEqual(plano["total_pernas"], 2)
        self.assertEqual(len(plano["destinos"]), 1)
        self.assertEqual(plano["destinos"][0]["unidade_administrativa_ids"], [101, 102])

    def test_despacho_multiplo_principal_fica_no_orgao_carta(self):
        demanda = self._demanda()
        resultado = DemandaDespachoService().despachar_multiplo(
            demanda,
            [{"secretaria_id": SINAPSE_ORGAO_B}],
            usuario=self.protocolo,
            texto_despacho="Despacho para secretaria competente e integrada.",
        )
        principal = resultado["demanda"]
        principal.refresh_from_db()
        self.assertEqual(principal.sinapse_orgao_id, SINAPSE_ORGAO_A)
        self.assertEqual(resultado["orgao_competente_id"], SINAPSE_ORGAO_A)
        self.assertEqual(len(resultado["demandas_desdobradas"]), 0)
        from core.models_perna_operacional import PernaOperacional

        self.assertEqual(PernaOperacional.objects.filter(demanda=principal).count(), 2)
        perna_b = PernaOperacional.objects.get(demanda=principal, sinapse_orgao_id=SINAPSE_ORGAO_B)
        self.assertEqual(perna_b.sinapse_orgao_id, SINAPSE_ORGAO_B)
