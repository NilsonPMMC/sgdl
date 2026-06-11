from django.test import TestCase
from unittest.mock import patch

from core.models import Usuario
from core.models_unidade_administrativa import (
    UnidadeAdministrativa,
    UnidadeAdministrativaResponsavel,
)
from core.services.usuario_vinculo_service import (
    PROTOCOLO_SINAPSE_ORGAO_ID,
    PROTOCOLO_UNIDADE_PK,
    PROTOCOLO_UNIDADE_SIGLA,
    UsuarioVinculoService,
)


class UsuarioVinculoProtocoloTests(TestCase):
    def setUp(self):
        self.ua_sgac, _ = UnidadeAdministrativa.objects.get_or_create(
            pk=PROTOCOLO_UNIDADE_PK,
            defaults={
                "sinapse_orgao_id": PROTOCOLO_SINAPSE_ORGAO_ID,
                "nome": "Seção de Gestão do Atendimento e Distribuição",
                "sigla": PROTOCOLO_UNIDADE_SIGLA,
                "sinapse_unidade_id": 110004543,
            },
        )
        self.service = UsuarioVinculoService()

    def test_criacao_protocolo_aplica_orgao_e_responsavel_via_signal(self):
        user = Usuario.objects.create_user(
            username="prot_u2",
            password="x",
            perfil="PROTOCOLO",
        )
        user.refresh_from_db()
        self.assertEqual(user.sinapse_orgao_id, PROTOCOLO_SINAPSE_ORGAO_ID)
        self.assertTrue(
            UnidadeAdministrativaResponsavel.objects.filter(
                usuario=user,
                unidade=self.ua_sgac,
                ativo=True,
            ).exists()
        )

    def test_sincronizar_protocolo_corrige_orgao_existente(self):
        user = Usuario.objects.create_user(
            username="prot_u2_fix",
            password="x",
            perfil="VEREADOR",
        )
        Usuario.objects.filter(pk=user.pk).update(
            perfil="PROTOCOLO",
            sinapse_orgao_id=99,
        )
        user.refresh_from_db()

        info = self.service.sincronizar_protocolo(user)
        user.refresh_from_db()

        self.assertTrue(info["orgao_atualizado"])
        self.assertEqual(user.sinapse_orgao_id, PROTOCOLO_SINAPSE_ORGAO_ID)
        self.assertTrue(info["unidade_encontrada"])

    def test_vereador_nao_recebe_vinculo(self):
        user = Usuario.objects.create_user(
            username="ver_u2",
            password="x",
            perfil="VEREADOR",
        )
        info = self.service.sincronizar_protocolo(user)
        self.assertFalse(info["orgao_atualizado"])
        self.assertFalse(
            UnidadeAdministrativaResponsavel.objects.filter(usuario=user).exists()
        )

    def test_resolver_unidade_protocolo_encontra_sgac(self):
        resolved = self.service.resolver_unidade_protocolo()
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.pk, self.ua_sgac.pk)


class UsuarioAtuacaoSgdlTests(TestCase):
    def setUp(self):
        self.ua_sgac, _ = UnidadeAdministrativa.objects.get_or_create(
            pk=PROTOCOLO_UNIDADE_PK,
            defaults={
                "sinapse_orgao_id": PROTOCOLO_SINAPSE_ORGAO_ID,
                "nome": "Seção de Gestão do Atendimento e Distribuição",
                "sigla": PROTOCOLO_UNIDADE_SIGLA,
                "sinapse_unidade_id": 110004543,
            },
        )
        self.service = UsuarioVinculoService()
        self._patch_orgao = patch(
            "integrations.sinapse_catalog.get_orgao_nome",
            side_effect=lambda oid: {12: "SMGOV", 3: "Saúde"}.get(oid, f"Órgão {oid}"),
        )
        self._patch_orgao.start()

    def tearDown(self):
        self._patch_orgao.stop()

    def test_vereador_sem_orgao_setor(self):
        user = Usuario.objects.create_user(username="ver_at", password="x", perfil="VEREADOR")
        atuacao = self.service.atuacao_sgdl(user)
        self.assertFalse(atuacao["requer_orgao"])
        self.assertTrue(atuacao["completa"])
        self.assertIn("sem órgão", atuacao["resumo"].lower())

    def test_protocolo_resumo_orgao_setor(self):
        user = Usuario.objects.create_user(username="prot_at", password="x", perfil="PROTOCOLO")
        self.service.sincronizar_protocolo(user)
        user.refresh_from_db()
        atuacao = self.service.atuacao_sgdl(user)
        self.assertTrue(atuacao["requer_orgao"])
        self.assertEqual(atuacao["orgao_id"], PROTOCOLO_SINAPSE_ORGAO_ID)
        self.assertIn("›", atuacao["resumo"])
        self.assertTrue(atuacao["completa"])

    def test_secretaria_incompleta(self):
        user = Usuario.objects.create_user(
            username="sec_at",
            password="x",
            perfil="SECRETARIA",
        )
        atuacao = self.service.atuacao_sgdl(user)
        self.assertFalse(atuacao["completa"])
        self.assertIn("Definir", atuacao["resumo"])

    def test_secretaria_completa(self):
        user = Usuario.objects.create_user(
            username="sec_ok",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=3,
        )
        ua = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=3,
            nome="Setor Teste",
            sigla="SET-TEST",
        )
        UnidadeAdministrativaResponsavel.objects.create(
            unidade=ua,
            usuario=user,
            ativo=True,
        )
        atuacao = self.service.atuacao_sgdl(user)
        self.assertTrue(atuacao["completa"])
        self.assertIn("›", atuacao["resumo"])
        self.assertIn("SET-TEST", atuacao["resumo"])
        self.assertIn("Saúde", atuacao["resumo"])
