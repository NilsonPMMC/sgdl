from .settings import *  # noqa

DEBUG = True
ENVIRONMENT = "test"


class _HomologTestDbCreation:
    """
    Reutiliza o Postgres de homologação nos testes (sem CREATE DATABASE).
    Necessário quando o usuário DB não tem permissão de criar banco.
    """

    @classmethod
    def patch(cls):
        from django.db.backends.base.creation import BaseDatabaseCreation

        if getattr(BaseDatabaseCreation._create_test_db, "_sgdl_homolog_patched", False):
            return

        original = BaseDatabaseCreation._create_test_db

        def _create_test_db(self, verbosity, autoclobber, keepdb=False):
            cfg = self.connection.settings_dict
            test_name = cfg.get("TEST", {}).get("NAME")
            main_name = cfg.get("NAME")
            if test_name and str(test_name) == str(main_name):
                if verbosity >= 1:
                    self.log(
                        "Reusing homolog database %s (no CREATE DATABASE)."
                        % self.connection.ops.quote_name(str(test_name))
                    )
                return str(test_name)
            return original(self, verbosity, autoclobber, keepdb)

        original_destroy = BaseDatabaseCreation._destroy_test_db

        def _destroy_test_db(self, test_database_name, verbosity):
            cfg = self.connection.settings_dict
            test_name = cfg.get("TEST", {}).get("NAME")
            main_name = cfg.get("NAME")
            if test_name and str(test_name) == str(main_name):
                if verbosity >= 1:
                    self.log(
                        "Preserving homolog database %s (no DROP DATABASE)."
                        % self.connection.ops.quote_name(str(test_name))
                    )
                return
            return original_destroy(self, test_database_name, verbosity)

        _create_test_db._sgdl_homolog_patched = True
        BaseDatabaseCreation._create_test_db = _create_test_db
        BaseDatabaseCreation._destroy_test_db = _destroy_test_db


_HomologTestDbCreation.patch()

# Postgres de homologação: reutiliza o banco principal com rollback transacional
# (ArrayField/pgvector não funcionam em SQLite sync).
_default_db = DATABASES["default"].copy()
_default_db.setdefault("TEST", {})
_default_db["TEST"]["NAME"] = _default_db["NAME"]
_sinapse_cfg = DATABASES.get("sinapse")

DATABASES = {"default": _default_db}

if _sinapse_cfg:
    DATABASES["sinapse"] = {
        **_sinapse_cfg,
        "TEST": {"MIRROR": "default"},
    }

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
