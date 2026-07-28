"""Testes da montagem do texto formal do ofício (B2)."""

from types import SimpleNamespace

from django.test import SimpleTestCase

from core.services.oficio_texto import montar_texto_oficio, montar_texto_oficio_lote


def _config_teste():
    return SimpleNamespace(
        municipio="Mogi das Cruzes",
        destinatario_tratamento="Excelentíssimo Senhor",
        destinatario_nome="Prefeito Municipal",
        destinatario_cargo="Prefeito Municipal",
        orgao_destinatario="Prefeitura Municipal",
        instituicao_nome="Câmara Municipal",
    )


class OficioTextoTests(SimpleTestCase):
    def test_data_aparece_apenas_no_cabecalho(self):
        texto = montar_texto_oficio(
            titulo="Buraco na via",
            relato="Solicito reparo.",
            endereco_formatado="Rua A, Centro",
            servico_nome="Manutenção viária",
            orgao_nome="Obras",
            autor_nome="Vereador Teste",
            autor_cargo="Vereador",
            config=_config_teste(),
        )
        linhas_data = [
            ln
            for ln in texto.splitlines()
            if any(
                m in ln.lower()
                for m in (
                    "janeiro",
                    "fevereiro",
                    "março",
                    "abril",
                    "maio",
                    "junho",
                    "julho",
                    "agosto",
                    "setembro",
                    "outubro",
                    "novembro",
                    "dezembro",
                )
            )
        ]
        self.assertEqual(len(linhas_data), 1)
        self.assertIn("Nestes termos, pede deferimento.", texto)
        fecho = texto.split("Nestes termos, pede deferimento.", 1)[1]
        self.assertNotIn("Mogi das Cruzes,", fecho.split("Vereador Teste")[0])

    def test_lote_sem_data_duplicada_no_fecho(self):
        texto = montar_texto_oficio_lote(
            itens=[
                {
                    "titulo": "Item 1",
                    "relato": "Descrição 1",
                    "servico_nome": "Serviço A",
                    "orgao_nome": "Secretaria A",
                }
            ],
            endereco_formatado="Rua B, Jardim",
            autor_nome="Vereador Lote",
            autor_cargo="Vereador",
            config=_config_teste(),
        )
        linhas_data = [
            ln
            for ln in texto.splitlines()
            if any(
                m in ln.lower()
                for m in (
                    "janeiro",
                    "fevereiro",
                    "março",
                    "abril",
                    "maio",
                    "junho",
                    "julho",
                    "agosto",
                    "setembro",
                    "outubro",
                    "novembro",
                    "dezembro",
                )
            )
        ]
        self.assertEqual(len(linhas_data), 1)
        self.assertTrue(texto.strip().endswith("Vereador"))
