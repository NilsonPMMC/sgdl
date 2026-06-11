import logging
import re
from contextlib import contextmanager
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


class SinapseClientError(Exception):
    """Erro de integração com base Sinapse."""


class SinapseClient:
    def __init__(self):
        self.db_name = settings.SINAPSE_DB_NAME
        self.db_user = settings.SINAPSE_DB_USER
        self.db_password = settings.SINAPSE_DB_PASSWORD
        self.db_host = settings.SINAPSE_DB_HOST
        self.db_port = settings.SINAPSE_DB_PORT

        if not all([self.db_name, self.db_user, self.db_password, self.db_host]):
            raise SinapseClientError(
                "Configuração do Sinapse incompleta. "
                "Defina SINAPSE_DB_NAME, SINAPSE_DB_USER, SINAPSE_DB_PASSWORD e SINAPSE_DB_HOST."
            )

    @contextmanager
    def _connection(self):
        try:
            import psycopg2
            import psycopg2.extras
        except Exception as exc:
            raise SinapseClientError(
                "Dependência de PostgreSQL ausente para integração Sinapse (psycopg2)."
            ) from exc

        conn = None
        try:
            conn = psycopg2.connect(
                dbname=self.db_name,
                user=self.db_user,
                password=self.db_password,
                host=self.db_host,
                port=self.db_port,
                connect_timeout=5,
            )
            yield conn, psycopg2.extras
        except Exception as exc:
            raise SinapseClientError(f"Falha ao conectar na base Sinapse: {exc}") from exc
        finally:
            if conn:
                conn.close()

    def test_connection(self) -> bool:
        with self._connection() as (conn, _):
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                row = cursor.fetchone()
                return bool(row and row[0] == 1)

    def list_candidate_tables(self, limit: int = 50) -> list[str]:
        sql = """
        SELECT table_schema || '.' || table_name AS full_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
          AND table_schema NOT IN ('pg_catalog', 'information_schema')
          AND (
            table_name ILIKE '%%servico%%'
            OR table_name ILIKE '%%carta%%'
            OR table_name ILIKE '%%service%%'
          )
        ORDER BY full_name
        LIMIT %s
        """
        with self._connection() as (conn, extras):
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cursor:
                cursor.execute(sql, (limit,))
                rows = cursor.fetchall()
                return [row["full_name"] for row in rows]

    def fetch_services(self, table_name: str, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?", table_name):
            raise SinapseClientError(f"Nome de tabela inválido para Sinapse: {table_name}")

        # table_name é de configuração interna controlada por equipe técnica.
        sql = f"SELECT * FROM {table_name} ORDER BY 1 LIMIT %s OFFSET %s"
        with self._connection() as (conn, extras):
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cursor:
                cursor.execute(sql, (limit, offset))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
