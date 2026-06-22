# Reprise VindIA — points à continuer avec Claude sur PC

État au 2026-06-08 (session VPS Rosco). Repo **public** `Davy-faugere/VindIA`.
CI verte vérifiée sur log réel. Working copy VPS : `/root/vindia-work`.

## Déjà fait (testé, vert)
- **Fondation agent** : `shared/agent/` — `session.py` (consentement), `audio/vad.py`
  (`VoiceSegmenter`), `audio/livekit_io.py` (`RoomSessionRegistry`, `HalfDuplexGate`,
  squelettes LiveKit), `runtime.py` (`ConversationRuntime` STT→LLM→TTS substituables,
  garde-fou consentement, audit), `ids.py` (CHAR(36)), `store.py` (DAO portable),
  `main.on_room_opened` (câblage).
- **BDD MariaDB** créée et validée (encodage **CHAR(36)**) : conteneur `vindia-mariadb`
  (localhost 127.0.0.1:3307), 6 tables. `docker-compose.yml` + `db/01-schema.sql`.
- **CI publique** verte (`.github/workflows/ci.yml`), **32 tests** stdlib (0 dépendance).
- Secrets hors git : `server/.env` (gitignoré) contient les mots de passe MariaDB générés.

## Bloqué — nécessite des secrets/crédentiels (à fournir par Davy)
1. **`MISTRAL_API_KEY`** (récup. « après ») → implémenter les adaptateurs STT (Voxtral)
   et LLM (Mistral) conformes aux `Protocol` de `runtime.py`.
2. **`LIVEKIT_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET`** → câbler `LiveKitRoomOut.play`
   (publication frames TTS) et `LiveKitAudioBridge.start` (abonnement pistes → VAD).
3. Dépendances runtime à installer sur le PC/VPS : `pip install -r requirements.txt`
   puis `livekit livekit-rtc mistralai` (à décommenter dans `requirements.txt`).

## Étapes de reprise (ordre conseillé)
1. ~~**Round-trip DB réel**~~ ✅ **FAIT (2026-06-22)** : `shared/agent/tests/test_store_integration.py`
   (opt-in `VINDIA_DB_IT=1` + `DB_DSN`, skippé en CI → 0-dépendance préservée). Round-trip
   tenant/member/binding/audit vert contre MariaDB, auto-nettoyant. `pymysql` installé sur le VPS.
2. ~~**Adaptateurs LLM/STT/TTS**~~ ✅ **FAIT (2026-06-22, mocks)** : `shared/agent/adapters.py`
   (`MistralLLM`/`VoxtralSTT`/`CallableTTS`, `transport` injectable, lazy-import). Tests mockés
   offline + end-to-end runtime. Reste le **live opt-in** dès clé Mistral dans `server/.env`.
3. **Câblage LiveKit** (dès creds) : `livekit_io.LiveKitRoomOut.play` et
   `LiveKitAudioBridge.start` (remplacer les `NotImplementedError`), puis `main.run()`
   (boucle de connexion + `on('room')`).
4. **Resolver diarisation→identité en prod** : brancher `store.make_member_resolver`
   sur la room courante ; remplir `speaker_bindings` à l'enrôlement.
5. **Audit en prod** : injecter `store.make_audit_sink(store, tenant_id)` dans le runtime.
6. **Durcir audit append-only** : privilèges DB (révoquer UPDATE/DELETE applicatifs) + trigger.
7. Monter la couverture vers la cible 63 tests au fil du câblage.

## Décisions déjà prises (ne pas redemander)
- Repo **public** (logs CI lisibles sans token ; PAT GitHub révoqué).
- Encodage ID **CHAR(36)** (pas BINARY(16)).
- MariaDB **localhost only** (jamais exposée).
- `0 dépendance` pour les tests unitaires / la CI ; deps runtime isolées hors CI.

## En attente côté Davy
- Fournir `MISTRAL_API_KEY` + `LIVEKIT_*`.
- Repo **site** `Site-EI-FAUGERE-DAVY` (privé, **distinct** de VindIA) : PAT lecture
  pour traiter pour de vrai sa CI (branche `fix/ci-green-smoke-e2e`, faux-vert E2E à retirer).
