from .settings import *  # noqa

DEBUG = True
ENVIRONMENT = "test"


class _KeepdbSqliteCreation:
    """Compatibilidade com --keepdb (legado SQLite)."""

    @classmethod
    def patch(cls):
        from django.db.backends.base import creation as creation_module

        if getattr(creation_module.BaseDatabaseCreation.create_test_db, "_sgdl_patched", False):
            return

        original = creation_module.BaseDatabaseCreation.create_test_db

        def create_test_db(self, verbosity=1, autoclobber=False, serialize=True, keepdb=False):
            import os

            test_name = self.connection.settings_dict["TEST"].get("NAME")
            if test_name is None:
                test_name = self._get_test_db_name()
            test_name = str(test_name)
            if keepdb and os.path.exists(test_name):
                self.connection.settings_dict["NAME"] = test_name
                self.connection.close()
                return test_name
            return original(self, verbosity, autoclobber, serialize, keepdb)

        create_test_db._sgdl_patched = True
        creation_module.BaseDatabaseCreation.create_test_db = create_test_db


_KeepdbSqliteCreation.patch()

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
