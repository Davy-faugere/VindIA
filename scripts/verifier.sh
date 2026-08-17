#!/usr/bin/env bash
# Contrôles à passer AVANT toute livraison. Chaque contrôle correspond à un bug
# réellement survenu en production — pas à une précaution théorique.
#
#   ./scripts/verifier.sh
#
# Sortie non nulle = ne pas livrer.
set -uo pipefail
cd "$(dirname "$0")/.."

ECHECS=0
ok()   { printf '  ok    %s\n' "$1"; }
echec() { printf '  ECHEC %s\n' "$1"; ECHECS=$((ECHECS+1)); }

echo "== Page web =="

# 1. Syntaxe JavaScript. Une erreur ici casse TOUTE la page, pas seulement la
#    fonction fautive.
python3 - <<'PY' > /tmp/verif_app.js 2>/dev/null
import re, pathlib
h = pathlib.Path('web/index.html').read_text(encoding='utf-8')
print(re.search(r'<script>(.*)</script>', h, re.S).group(1))
PY
if node --check /tmp/verif_app.js >/dev/null 2>&1; then ok "syntaxe JavaScript"; else
  echec "syntaxe JavaScript"; node --check /tmp/verif_app.js 2>&1 | head -3; fi

# 2. Éléments appelés mais absents du HTML. C'est le bug « le bouton ne fait
#    rien » : $('svcNote') renvoyait null, l'erreur était avalée par le
#    gestionnaire de clic et le formulaire restait inerte.
MANQUANTS=$(python3 - <<'PY'
import re, pathlib
h = pathlib.Path('web/index.html').read_text(encoding='utf-8')
js = re.search(r'<script>(.*)</script>', h, re.S).group(1)
ids = set(re.findall(r'id="([^"]+)"', h))
print(" ".join(sorted({m for m in re.findall(r"\$\('([^']+)'\)", js)} - ids)))
PY
)
if [ -z "$MANQUANTS" ]; then ok "tous les éléments appelés existent"; else
  echec "éléments appelés mais absents du HTML : $MANQUANTS"; fi

# 3. Accolades CSS. Un bloc non fermé fait sauter toute la mise en page.
if python3 - <<'PY'
import re, pathlib, sys
css = re.search(r'<style>(.*?)</style>',
                pathlib.Path('web/index.html').read_text(encoding='utf-8'), re.S).group(1)
sys.exit(0 if css.count('{') == css.count('}') else 1)
PY
then ok "accolades CSS équilibrées"; else echec "accolades CSS déséquilibrées"; fi

# 4. Version du cache. Sans incrément, l'utilisateur garde l'ancienne page et
#    croit que le correctif n'a pas été livré.
if git diff --quiet HEAD -- web/index.html 2>/dev/null || ! git diff --quiet HEAD -- web/sw.js 2>/dev/null; then
  ok "version du cache cohérente avec la page"
else
  echec "web/index.html modifié sans incrémenter CACHE dans web/sw.js"
fi

echo "== Serveur =="

# 5. Le serveur démarre-t-il ? Un import cassé et plus rien ne répond.
if [ -f server/.env ]; then
  if ( set -a; . server/.env; set +a; .venv/bin/python -c "import web.server as s; s.build_app()" ) >/dev/null 2>&1
  then ok "le serveur s'importe et construit ses routes"
  else echec "le serveur ne démarre pas"
       ( set -a; . server/.env; set +a; .venv/bin/python -c "import web.server as s; s.build_app()" ) 2>&1 | tail -4
  fi
else
  printf '  passé server/.env absent\n'
fi

echo "== Tests =="
if .venv/bin/python -m pytest shared/agent/tests -q >/tmp/verif_tests.txt 2>&1; then
  ok "$(tail -1 /tmp/verif_tests.txt)"
else
  echec "tests en échec"; tail -12 /tmp/verif_tests.txt
fi

echo
if [ "$ECHECS" -eq 0 ]; then echo "Tout est vert — livraison possible."; else
  echo "$ECHECS contrôle(s) en échec — NE PAS LIVRER."; fi
exit "$ECHECS"
