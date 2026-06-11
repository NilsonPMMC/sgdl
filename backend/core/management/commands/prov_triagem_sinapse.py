"""Prova a triagem Sinapse (Kernel → embedding 1024 → pgvector + merge lexical).

Uso:
  cd backend && python manage.py prov_triagem_sinapse "buraco na rua x"
  SINAPSE_TRIAGEM_LOG=true python manage.py prov_triagem_sinapse "buraco"

Exige DATABASES['sinapse'] configurado (.env) e Kernel AI acessível para embedding.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from core.services.triagem_service import TriagemService
from core.services.vector_service import VectorService


class Command(BaseCommand):
    help = "Exibe embedding (dim/modelo) e o ranking Sinapse (pgvector + opcional merge lexical)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "texto",
            nargs="?",
            default="buraco na rua maestro laurindo josé gonçalves parque santana",
            help="Texto para gerar embedding e consultar a carta",
        )
        parser.add_argument(
            "--top",
            type=int,
            default=8,
            help="Quantidade de resultados",
        )
        parser.add_argument(
            "--sem-lexical",
            action="store_true",
            help="Desliga merge lexical (só pgvector)",
        )

    def handle(self, *args, **opts) -> None:
        texto = (opts.get("texto") or "").strip()
        top = max(1, min(int(opts.get("top") or 8), 25))
        sem_lexical = bool(opts.get("sem_lexical"))

        if "sinapse" not in settings.DATABASES:
            self.stderr.write(
                self.style.ERROR(
                    "DATABASES['sinapse'] não configurado. Defina SINAPSE_DB_* no .env."
                )
            )
            return

        modelo = getattr(settings, "AI_KERNEL_EMBEDDING_MODEL", "?")
        base = getattr(settings, "AI_KERNEL_BASE_URL", "?")
        self.stdout.write(f"Kernel URL: {base}")
        self.stdout.write(f"Modelo embedding: {modelo}")

        vetor = VectorService().generate_embedding(texto)
        if not vetor:
            self.stderr.write(
                self.style.ERROR(
                    "Embedding vazio (Kernel indisponível ou resposta inválida). "
                    "Verifique AI_KERNEL_BASE_URL e logs."
                )
            )
            return

        self.stdout.write(f"Dimensões do vetor de consulta: {len(vetor)} (Sinapse espera 1024)")
        if len(vetor) != 1024:
            self.stderr.write(
                self.style.WARNING(
                    "Atenção: dimensão != 1024 invalida comparação correta com catalog_servico.embedding."
                )
            )

        triagem = TriagemService()
        if sem_lexical:
            raw = triagem._buscar_via_pgvector(vetor, top)
            self.stdout.write(self.style.NOTICE("\n--- Somente pgvector (sem merge lexical) ---"))
            for r in raw:
                self._write_linha(r)
            return

        res = triagem.buscar_servico_sinapse(vetor, top_k=top, texto_consulta=texto)
        self.stdout.write(
            self.style.NOTICE(
                f"\n--- Ranking final (pgvector + merge lexical={settings.SINAPSE_TRIAGEM_LEXICAL_MERGE}) ---"
            )
        )
        if not res:
            self.stdout.write(self.style.WARNING("Nenhum candidato retornado."))
            return
        for r in res:
            self._write_linha(r)

    def _write_linha(self, r: dict) -> None:
        sid = r.get("servico_id")
        tit = (r.get("titulo") or "")[:90]
        sc = r.get("score")
        dist = r.get("distancia")
        org = r.get("orgao") or ""
        scs = f" score={sc}" if sc is not None else " score=(lexical)"
        dst = f" dist={dist}" if dist is not None else ""
        self.stdout.write(
            f"  id={sid}{scs}{dst} orgao={org[:40]!r}\n       titulo={tit!r}"
        )
