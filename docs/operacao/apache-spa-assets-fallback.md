# Patch Apache — assets JS não devem cair no FallbackResource do SPA

Aplicar em `/etc/apache2/sites-available/sgdl.conf` (substituir bloco §4):

```apache
    # --- 4. Configuração do SPA (Vue) ---
    # Assets com hash: 404 real se chunk não existir (evita MIME text/html em .js antigo).
    <Directory /var/www/sgdl/frontend/dist/assets>
        Options -MultiViews
        Require all granted
        FallbackResource disabled
    </Directory>

    <Directory /var/www/sgdl/frontend/dist>
        Options Indexes FollowSymLinks
        AllowOverride All
        Require all granted
        FallbackResource /index.html
    </Directory>
```

Depois:

```bash
sudo apache2ctl configtest
sudo systemctl reload apache2
```

Validação:

```bash
curl -sI "https://sgdl.mogidascruzes.sp.gov.br/assets/index-Cz-rK7Hx.js" | grep -i content-type
# Esperado após patch: 404 (ou text/plain), NÃO text/html
```

## Sintoma

`Failed to load module script ... MIME type of "text/html"` — navegador com `index.html` antigo em cache apontando para chunk que não existe mais; Apache devolvia `index.html` no lugar do `.js`.

## Mitigação imediata (operador)

Hard refresh: **Ctrl+Shift+R** (ou abrir em aba anônima).
