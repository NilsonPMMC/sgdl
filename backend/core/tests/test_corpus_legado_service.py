"""Testes do corpus legado (aprendizado, sem Demandas)."""

import json
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from core.services.corpus_legado_service import (
    analisar_corpus,
    carregar_linhas_csv,
    corpus_legado_csv_path,
)


class CorpusLegadoServiceTests(SimpleTestCase):
    def test_csv_legado_carrega(self):
        path = corpus_legado_csv_path()
        if not path.is_file():
            self.skipTest(f"CSV ausente: {path}")
        linhas = carregar_linhas_csv(path)
        self.assertGreater(len(linhas), 1000)
        self.assertIn("assunto", linhas[0])

    def test_analisar_produz_top_trends(self):
        path = corpus_legado_csv_path()
        if not path.is_file():
            self.skipTest(f"CSV ausente: {path}")
        linhas = carregar_linhas_csv(path)
        rel = analisar_corpus(linhas, checksum="test")
        self.assertGreater(rel["total_registros"], 1000)
        trends = rel["top_trends"]
        self.assertGreaterEqual(len(trends), 10)
        self.assertEqual(trends[0]["servico_legado"], "Limpeza Pública")
        self.assertIn("atalho_sugerido", trends[0])
        self.assertGreater(len(rel["top_setores"]), 5)

    def test_sugerir_por_texto(self):
        import tempfile
        from core.services.corpus_legado_service import CorpusLegadoService, gerar_relatorio_corpus

        csv = corpus_legado_csv_path()
        if not csv.is_file():
            self.skipTest("CSV ausente")
        with tempfile.TemporaryDirectory() as tmp:
            json_out = Path(tmp) / "corpus.json"
            gerar_relatorio_corpus(csv_path=csv, json_path=json_out)
            with override_settings(
                CORPUS_LEGADO_ENABLED=True,
                CORPUS_LEGADO_JSON_PATH=str(json_out),
            ):
                svc = CorpusLegadoService()
                vazio = svc.sugerir_por_texto("ab")
                self.assertEqual(vazio, [])
                hits = svc.sugerir_por_texto("tapa buraco na rua principal do bairro")
        self.assertGreaterEqual(len(hits), 1)
        self.assertIn("Recapeamento", hits[0].get("servico_legado", ""))

    def test_atalhos_usa_json_quando_existe(self):
        import tempfile
        from core.services.corpus_legado_service import CorpusLegadoService, gerar_relatorio_corpus

        csv = corpus_legado_csv_path()
        if not csv.is_file():
            self.skipTest("CSV ausente")
        with tempfile.TemporaryDirectory() as tmp:
            json_out = Path(tmp) / "corpus.json"
            gerar_relatorio_corpus(csv_path=csv, json_path=json_out)
            with override_settings(
                CORPUS_LEGADO_ENABLED=True,
                CORPUS_LEGADO_JSON_PATH=str(json_out),
            ):
                atalhos = CorpusLegadoService().atalhos_copiloto(limite=8)
        self.assertGreaterEqual(len(atalhos), 5)
        self.assertIn("ranking", atalhos[0])
        self.assertIn("rotulo", atalhos[0])
        self.assertNotEqual((atalhos[0].get("rotulo") or "").lower(), "outros")
        rotulos = {(a.get("rotulo") or "").lower() for a in atalhos}
        self.assertNotIn("outros", rotulos)

    def test_opcoes_carta_iluminacao(self):
        import tempfile
        from core.services.corpus_legado_service import CorpusLegadoService, gerar_relatorio_corpus

        csv = corpus_legado_csv_path()
        if not csv.is_file():
            self.skipTest("CSV ausente")
        with tempfile.TemporaryDirectory() as tmp:
            json_out = Path(tmp) / "corpus.json"
            gerar_relatorio_corpus(csv_path=csv, json_path=json_out)
            with override_settings(
                CORPUS_LEGADO_ENABLED=True,
                CORPUS_LEGADO_JSON_PATH=str(json_out),
            ):
                det = CorpusLegadoService().detalhe_atalho_copiloto("iluminacao")
        if not det:
            self.skipTest("Sinapse indisponível")
        opcoes = det.get("opcoes_carta") or []
        if not opcoes:
            self.skipTest("Catálogo Sinapse indisponível no ambiente de teste")
        self.assertGreaterEqual(len(opcoes), 3)
        titulos = " ".join(o.get("titulo", "") for o in opcoes).lower()
        self.assertIn("iluminação pública", titulos)
        self.assertNotIn("cip", titulos)
        self.assertTrue(any(o.get("servico_id") == 14 for o in opcoes))

    def test_detectar_eixo_manutencao_estrada(self):
        from core.services.corpus_legado_service import CorpusLegadoService

        meta = CorpusLegadoService().detectar_eixo_por_texto(
            "Solicito manutenção de estrada (informe via e bairro)."
        )
        self.assertIsNotNone(meta)
        self.assertEqual(meta.get("eixo_id"), "vias_buracos_nivelamento")

    def test_hints_carta_manutencao_estrada(self):
        import tempfile
        from core.services.corpus_legado_service import CorpusLegadoService, gerar_relatorio_corpus

        csv = corpus_legado_csv_path()
        if not csv.is_file():
            self.skipTest("CSV ausente")
        with tempfile.TemporaryDirectory() as tmp:
            json_out = Path(tmp) / "corpus.json"
            gerar_relatorio_corpus(csv_path=csv, json_path=json_out)
            with override_settings(
                CORPUS_LEGADO_ENABLED=True,
                CORPUS_LEGADO_JSON_PATH=str(json_out),
            ):
                hints = CorpusLegadoService().hints_carta_por_texto(
                    "Solicito manutenção de estrada via rural do bairro"
                )
        if not hints:
            self.skipTest("Sinapse indisponível")
        titulo = (hints[0].get("titulo_sinapse_historico") or "").lower()
        self.assertTrue(
            "nivelamento" in titulo or "cascalh" in titulo,
            msg=f"Esperado serviço de estrada, obteve: {hints[0]}",
        )

    def test_hints_carta_por_texto_iluminacao(self):
        import tempfile
        from core.services.corpus_legado_service import CorpusLegadoService, gerar_relatorio_corpus

        csv = corpus_legado_csv_path()
        if not csv.is_file():
            self.skipTest("CSV ausente")
        with tempfile.TemporaryDirectory() as tmp:
            json_out = Path(tmp) / "corpus.json"
            gerar_relatorio_corpus(csv_path=csv, json_path=json_out)
            with override_settings(
                CORPUS_LEGADO_ENABLED=True,
                CORPUS_LEGADO_JSON_PATH=str(json_out),
            ):
                hints = CorpusLegadoService().hints_carta_por_texto(
                    "Solicito iluminação pública R. João Ribeiro, 114 - Vila Suissa"
                )
        if not hints:
            self.skipTest("Sinapse indisponível")
        self.assertGreaterEqual(len(hints), 3)
        self.assertEqual(hints[0].get("fonte"), "carta_eixo")
        self.assertIn("titulo_sinapse_historico", hints[0])

    def test_depara_enriquece_sugestao(self):
        import tempfile
        from core.services.corpus_legado_service import CorpusLegadoService, gerar_relatorio_corpus

        csv = corpus_legado_csv_path()
        if not csv.is_file():
            self.skipTest("CSV ausente")
        depara = {
            "versao": 1,
            "mapeamentos": [
                {
                    "servico_legado": "Recapeamento/Tapa Buraco",
                    "sinapse_servico_id": 80,
                    "titulo_sinapse": "Tapa Buraco",
                    "confianca": "alta",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            json_out = Path(tmp) / "corpus.json"
            depara_out = Path(tmp) / "depara.json"
            gerar_relatorio_corpus(csv_path=csv, json_path=json_out)
            depara_out.write_text(json.dumps(depara), encoding="utf-8")
            with override_settings(
                CORPUS_LEGADO_ENABLED=True,
                CORPUS_LEGADO_JSON_PATH=str(json_out),
                CORPUS_LEGADO_DEPARA_PATH=str(depara_out),
            ):
                svc = CorpusLegadoService()
                dep = svc.resolver_depara_legado("Recapeamento/Tapa Buraco")
                self.assertEqual(dep.get("sinapse_servico_id"), 80)
                enr = svc.enriquecer_sugestao_depara(
                    {"servico_legado": "Recapeamento/Tapa Buraco", "volume": 916}
                )
                self.assertEqual(enr.get("sinapse_servico_id_sugerido_historico"), 80)
                self.assertEqual(enr.get("titulo_sinapse_historico"), "Tapa Buraco")

    def test_hints_pos_triagem_com_texto(self):
        import tempfile
        from core.services.corpus_legado_service import CorpusLegadoService, gerar_relatorio_corpus

        csv = corpus_legado_csv_path()
        if not csv.is_file():
            self.skipTest("CSV ausente")
        with tempfile.TemporaryDirectory() as tmp:
            json_out = Path(tmp) / "corpus.json"
            gerar_relatorio_corpus(csv_path=csv, json_path=json_out)
            with override_settings(
                CORPUS_LEGADO_ENABLED=True,
                CORPUS_LEGADO_JSON_PATH=str(json_out),
            ):
                hints = CorpusLegadoService().hints_pos_triagem(
                    "tapa buraco na rua principal do bairro centro",
                    limite=2,
                )
        self.assertGreaterEqual(len(hints), 1)
        self.assertIn("servico_legado", hints[0])
