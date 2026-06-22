# Dossier d'avancement — VindIA R&D

> Journal daté. Le plus récent en haut. Politique : 0 hallucination, tout sourcé.

## État du moment (2026-06-22)

- **Phase** : J0 — Cadrage R&D (préparation + identification des blocages).
- **Foyer Notion** : page « VindIA — R&D » à créer **sous *Atelier Produits*** (décision : aucune page
  projet VindIA dédiée n'existait, d'où la confusion « je ne trouve pas VindIA dans Notion »).
- **Canaux de notification retenus** : Push app Claude Code + Google Calendar.
- **Périmètre voix retenu** : cap sur la **cible souveraine VindIA** (Voxtral/Mistral/LiveKit).
- **Conséquence directe** : les **credentials** (`MISTRAL_API_KEY`, `LIVEKIT_*`) deviennent le
  **blocage n°1** (cf. [`02-REGISTRE-BLOCAGES.md`](./02-REGISTRE-BLOCAGES.md)).

## Session 2026-06-22 — « Préparation & blocages »

### Fait
- Lecture intégrale de la fondation existante (`README`, `docs/*`, `docker-compose.yml`,
  `requirements.txt`) : VindIA dispose déjà d'un pipeline STT→LLM→TTS substituable testé, d'un
  schéma MariaDB validé (CHAR(36)), d'une CI verte 32 tests, et d'un fichier `REPRISE-PC.md`
  listant déjà des blocages credentials.
- **R&D sourcée** lancée en fan-out (≈9 angles), agents terminés :
  1. Voxtral (STT/STU/realtime/TTS) — modèles, langues FR, latence, diarisation, tarifs.
  2. Mistral LLM 2025-2026 — catalogue, tool-calling, latence streaming, dispo EU.
  3. LiveKit Agents — `AgentSession`, turn detection v1, barge-in adaptatif, plugin `mistralai`.
  4. TTS souverains FR — Kyutai TTS 1.6B / Pocket, Piper, Coqui XTTS, Voxtral TTS, Kokoro (licences).
  5. Silero VAD + turn detection — tailles, latences, EOT-Bench.
  6. Latence/turn-taking — budgets, seuils humains ~200 ms, AEC/echo, full vs half-duplex.
  7. Diarisation — DER réel, NVIDIA Sortformer, échecs multi-locuteurs.
  8. Hallucinations & robustesse — RAG grounding, abstention, WebRTC, observabilité.
  9. Skills/MCP — tool-calling, MCP, Agent Skills (SKILL.md), benchmarks, guardrails, fiabilité.
- Rédaction des livrables : cahier des charges, veille sourcée, registre blocages, algorigrammes,
  catalogue skills.

### Décisions prises (ne pas redemander)
- Espace R&D Notion **sous Atelier Produits** (page dédiée « VindIA — R&D » à créer).
- Notifications via **Push Claude Code + Google Calendar**.
- Cap **cible souveraine** (pas de prototype non-EU intermédiaire).
- Politique documentaire **0 hallucination** : sources primaires + marqueurs `[INCERTAIN]`/`[NON TROUVÉ]`.

### Prochaines actions (ordre conseillé)
1. **[Davy]** Fournir `MISTRAL_API_KEY` + `LIVEKIT_URL/API_KEY/API_SECRET` → débloque J3/J4 (B-001).
2. **[Claude]** Préparer les adaptateurs STT/LLM/TTS (squelettes conformes aux `Protocol`) + tests mockés,
   prêts à brancher dès réception des clés.
3. **[Claude]** Préparer le test d'intégration MariaDB *opt-in* (gardé par variable d'env).
4. **[Claude]** Arbitrer la brique **TTS** : Voxtral TTS (API, simple) vs Kyutai TTS 1.6B (self-host, FR mesuré)
   — dépend du modèle commercial et de la contrainte GPU (cf. veille §TTS).
5. **[Davy/Claude]** Planifier la 1ʳᵉ **session de test vocal** (Google Calendar) une fois J3/J4 prêts.

### Métriques cibles à instrumenter dès le 1er test (sourcées — voir §03)
- Latence E2E perçue (fin parole → 1er son agent) : objectif **< 700 ms**.
- False barge-in rate : cible **< 2–5 %**.
- WER FR (STT) : référence Voxtral Mini ~5,75 % (FLEURS).
- Disponibilité audit (chaînage/immuabilité) : vérifiable.

## Backlog d'informations à récupérer (prochaines sessions)
- Confirmer les **tarifs API** Voxtral TTS / Realtime sur La Plateforme (`[NON TROUVÉ]`).
- Vérifier **diarisation** disponible en streaming temps réel (Voxtral realtime = non ; batch = oui).
- Trancher la **classification AI Act** du cas d'usage précis (risque limité vs Annexe III).
- Statut **transposition NIS2 France** (loi non promulguée au 2026-06-22).
- Faisabilité **barge-in adaptatif self-host** (actuellement cloud-only chez LiveKit, issue #6033).
