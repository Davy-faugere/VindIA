"""Coffre à credentials chiffré, isolé par membre (Lot 2c).

VindIA stocke des jetons d'accès aux comptes des utilisateurs (Google, mail,
Notion…). Deux garanties NON négociables :

  - CHIFFREMENT AU REPOS. Les secrets (tokens OAuth, mots de passe d'app) ne
    touchent JAMAIS le disque en clair : ils sont chiffrés via un `Crypto`
    injecté. En prod = Fernet (AES-128 authentifié, lib `cryptography`). La clé
    vit hors du dépôt (env `VINDIA_VAULT_KEY`), jamais commitée.
  - ISOLATION PAR MEMBRE. Tout est rangé sous `<base>/<member_id>/connections/`.
    `member_id` est assaini (anti path-traversal) : un membre ne lit/écrit QUE
    son coffre. Le `member_id` découle du code d'accès côté serveur.

Le `Crypto` est INJECTABLE (pattern maison) : la CI teste la logique du coffre
avec un chiffreur réversible factice → 0 dépendance, 100 % offline. Le vrai
Fernet est construit paresseusement en prod. `meta` (non sensible : e-mail, scopes)
reste en clair pour pouvoir l'afficher ; seuls les `secrets` sont chiffrés.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Protocol

# member_id VindIA = UUID CHAR(36). Tout le reste est rejeté (cf. projects.py).
_MEMBER_RE = re.compile(r"^[0-9a-fA-F-]{1,36}$")
_SERVICE_RE = re.compile(r"[^a-z0-9_-]+")


def _safe_member(member_id: str) -> str:
    if not member_id or not _MEMBER_RE.match(member_id):
        raise ValueError("member_id invalide")
    return member_id


def _safe_service(service: str) -> str:
    s = _SERVICE_RE.sub("-", (service or "").strip().lower()).strip("-")
    if not s:
        raise ValueError("nom de service invalide")
    return s[:40]


class Crypto(Protocol):
    """Chiffre/déchiffre une chaîne. Implémentations : Fernet (prod), fake (test)."""

    def encrypt(self, plaintext: str) -> str: ...
    def decrypt(self, token: str) -> str: ...


def fernet_crypto(key: str) -> Crypto:  # pragma: no cover - dépend de cryptography
    """Chiffreur Fernet (prod). `key` = clé Fernet base64 urlsafe (32 octets).

    Génération d'une clé : `Fernet.generate_key().decode()` (à mettre dans
    l'environnement, jamais dans le dépôt).
    """
    from cryptography.fernet import Fernet

    f = Fernet(key.encode() if isinstance(key, str) else key)

    class _FernetCrypto:
        def encrypt(self, plaintext: str) -> str:
            return f.encrypt(plaintext.encode("utf-8")).decode("ascii")

        def decrypt(self, token: str) -> str:
            return f.decrypt(token.encode("ascii")).decode("utf-8")

    return _FernetCrypto()


class Connection:
    """Vue non sensible d'une connexion (jamais les secrets)."""

    def __init__(self, service: str, meta: dict, connected_at: str) -> None:
        self.service = service
        self.meta = meta
        self.connected_at = connected_at

    def as_dict(self) -> dict:
        return {"service": self.service, "connected": True, "meta": self.meta, "connected_at": self.connected_at}


class CredentialVault:
    """Stockage chiffré des connexions d'un membre.

    Fichier par service : `<base>/<member_id>/connections/<service>.json`
      { service, meta(clair), secret(chiffré: JSON des secrets), connected_at }
    """

    def __init__(self, base_dir: str, crypto: Crypto, *, clock=None) -> None:
        self._base = Path(base_dir)
        self._crypto = crypto
        self._clock = clock or _default_clock

    def _conn_dir(self, member_id: str) -> Path:
        return self._base / _safe_member(member_id) / "connections"

    def _conn_path(self, member_id: str, service: str) -> Path:
        return self._conn_dir(member_id) / f"{_safe_service(service)}.json"

    def store(self, member_id: str, service: str, secrets: dict, meta: Optional[dict] = None) -> Connection:
        """Chiffre `secrets` et persiste la connexion. `meta` reste en clair (affichable)."""
        svc = _safe_service(service)
        cdir = self._conn_dir(member_id)
        cdir.mkdir(parents=True, exist_ok=True)
        ts = self._clock()
        record = {
            "service": svc,
            "meta": meta or {},
            "secret": self._crypto.encrypt(json.dumps(secrets, ensure_ascii=False)),
            "connected_at": ts,
        }
        self._conn_path(member_id, svc).write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return Connection(svc, record["meta"], ts)

    def get_secrets(self, member_id: str, service: str) -> Optional[dict]:
        """Déchiffre et retourne les secrets d'une connexion, ou None si absente."""
        path = self._conn_path(member_id, service)
        if not path.is_file():
            return None
        record = json.loads(path.read_text(encoding="utf-8"))
        raw = self._crypto.decrypt(record["secret"])
        return json.loads(raw)

    def get_meta(self, member_id: str, service: str) -> Optional[dict]:
        path = self._conn_path(member_id, service)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8")).get("meta", {})

    def list_connections(self, member_id: str) -> List[Connection]:
        """Connexions du membre, SANS jamais déchiffrer ni exposer les secrets."""
        cdir = self._conn_dir(member_id)
        if not cdir.exists():
            return []
        out: List[Connection] = []
        for f in sorted(cdir.glob("*.json")):
            rec = json.loads(f.read_text(encoding="utf-8"))
            out.append(Connection(rec["service"], rec.get("meta", {}), rec.get("connected_at", "")))
        return out

    def is_connected(self, member_id: str, service: str) -> bool:
        return self._conn_path(member_id, service).is_file()

    def delete(self, member_id: str, service: str) -> bool:
        path = self._conn_path(member_id, service)
        if path.is_file():
            path.unlink()
            return True
        return False


def _default_clock() -> str:  # pragma: no cover - dépend de l'heure réelle
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
