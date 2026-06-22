# Cahier des charges — VindIA (agent vocal conversationnel souverain)

> Version 0.1 — 2026-06-22. Document vivant ; révisé à chaque jalon.
> Statut : **cadrage R&D**. Les chiffres techniques cités proviennent de la veille sourcée
> ([`03-VEILLE-SOURCEE.md`](./03-VEILLE-SOURCEE.md)).

## 1. Vision

Un **agent vocal conversationnel temps réel** : l'utilisateur parle, l'agent comprend, raisonne et
**répond avec une voix naturelle**, avec une latence proche de la conversation humaine. VindIA est
**souverain (UE)** et **compliant by design** (RGPD, EU AI Act art. 50, ALCOA+ sur l'audit).

VindIA doit pouvoir **acquérir des compétences (« skills »)** réutilisables et fiables (outils,
function-calling, MCP), évolutives pas à pas.

## 2. Périmètre

### Dans le périmètre (V1)
- Conversation vocale **bidirectionnelle** en **français** (modèles multilingues).
- Pipeline en cascade **STT → LLM → TTS** orchestré par LiveKit Agents (streaming bout-en-bout).
- **Détection de tour de parole** (turn detection) + **barge-in** (interruption) + **anti-larsen**.
- **Consentement explicite** et **mention « vous parlez à une IA »** (AI Act art. 50).
- **Audit append-only** des interactions (ALCOA+).
- **Catalogue de skills** v1 (au moins : recherche, mémoire de session, accès à un outil métier).
- **Multi-locuteur** géré par diarisation → résolution vers `member_id` (jamais identité biométrique).

### Hors périmètre (V1, à réévaluer)
- Reconnaissance/identification **biométrique** par empreinte vocale (régime art. 9 RGPD — évité).
- Reconnaissance **d'émotions** en contexte travail/éducation (interdit AI Act art. 5(1)(f)).
- Full-duplex « vrai » (parler et écouter simultanément) — V1 = half-duplex + barge-in.
- Téléphonie (SIP) — V2.

## 3. Acteurs & cas d'usage

- **Davy (testeur/pilote)** : parle à VindIA, valide pas à pas, reçoit notifications.
- **Utilisateur final** : interagit en voix ; informé qu'il parle à une IA ; consent au traitement.
- **Agent VindIA** : écoute → transcrit → raisonne (LLM + skills) → répond en voix.

Cas d'usage V1 prioritaire : **assistant conversationnel personnel testable** (Davy parle, VindIA
répond), servant de banc d'essai pour mesurer latence, qualité voix FR, turn-taking, fiabilité skills.

## 4. Exigences fonctionnelles

| Réf | Exigence |
|---|---|
| F1 | Capter l'audio entrant via LiveKit (WebRTC) et segmenter la voix (VAD). |
| F2 | Transcrire en temps réel (STT Voxtral streaming) avec latence configurable. |
| F3 | Détecter la fin de tour (turn detection) avant d'invoquer le LLM. |
| F4 | Générer une réponse via LLM Mistral, avec **tool/function-calling** (skills). |
| F5 | Synthétiser la réponse en voix (TTS) et la diffuser dans la room (streaming). |
| F6 | Gérer le **barge-in** : si l'utilisateur parle pendant la réponse, couper le TTS. |
| F7 | Afficher/énoncer la **mention IA** au premier contact + recueillir le **consentement**. |
| F8 | Journaliser chaque interaction dans un **audit append-only** (qui/quoi/quand). |
| F9 | Résoudre les labels de diarisation (`speaker_id`) vers un `member_id` applicatif. |
| F10 | Exécuter des **skills** déclenchées par l'intention (catalogue extensible). |

## 5. Exigences non fonctionnelles

| Réf | Exigence | Cible (sourcée — voir §03) |
|---|---|---|
| NF1 | **Latence bout-en-bout** perçue (fin de parole → 1er son agent). | Objectif **< 700 ms** côté agent ; idéal ~400–500 ms streaming optimisé. Référence humaine ~200–300 ms. `[cible d'ingénierie, à mesurer]` |
| NF2 | Latence STT (1er token). | Voxtral realtime : délai configurable, point optimal documenté **~480 ms** ; sub-200 ms possible selon réglage. `[INCERTAIN sur la valeur exacte]` |
| NF3 | Latence TTS (1er audio). | TTS streaming ~70–220 ms (modèle) ; TTFB réel dépend de l'hébergement. |
| NF4 | **Souveraineté** : données traitées et hébergées en UE/EEE. | Hébergement EU ; sous-traitants sous DPA art. 28 ; pas de transfert hors UE sans CCT. |
| NF5 | **Disponibilité audit** : logs immuables, chaînés. | WORM / hash-chaining ; séparation des droits (pas d'UPDATE/DELETE applicatif). |
| NF6 | **Substituabilité** : STT/LLM/TTS = composants interchangeables. | Contrats `Protocol` Python (déjà posés dans `runtime.py`). |
| NF7 | **Fiabilité skills** : sorties d'outils validées, garde-fous, abstention. | Grounding + validation schéma ; abstention « je ne sais pas » si confiance faible. |
| NF8 | **Anti-larsen** : pas de boucle audio. | Casques + half-duplex (`HalfDuplexGate`) ; AEC si haut-parleur ouvert. |

## 6. Contraintes de souveraineté & conformité (résumé — détail en §03)

- **AI Act art. 50** (applicable **2 août 2026**) : informer clairement l'utilisateur qu'il parle à une IA.
- **AI Act art. 5(1)(f)** (applicable depuis 2 fév. 2025) : pas de reconnaissance d'émotions au travail/éducation.
- **RGPD** : base légale (art. 6) ; si identification vocale → art. 9 + consentement explicite (évité en V1) ;
  **AIPD probablement requise** (EDPB 02/2021) ; minimisation, durées de conservation, droits des personnes.
- **Diarisation ≠ biométrie** tant qu'aucune identification unique n'est visée ; prudence sur les empreintes intermédiaires.
- **NIS2** : applicable selon taille/secteur ; transposition FR **non encore promulguée** au 2026-06-22 `[à confirmer]`.
- **ALCOA+** : cadre d'intégrité (origine pharma) transposé par analogie à l'audit log.

## 7. Architecture cible (vue d'ensemble)

```
Utilisateur (casque)
      │ WebRTC
      ▼
  LiveKit Room ──► VAD (Silero) ──► Turn detection ──► STT (Voxtral realtime)
      ▲                                                      │
      │ TTS audio (streaming)                                ▼
  RoomOut ◄── TTS (Voxtral TTS / Kyutai) ◄── LLM (Mistral + skills/tool-calling)
                                                  │
                                          Skills (MCP / function-calling)
                                                  │
                                   Audit append-only + résolveur diarisation→member
```

Détail + algorigrammes : [`04-ARCHITECTURE-ALGORIGRAMME.md`](./04-ARCHITECTURE-ALGORIGRAMME.md).

## 8. Stack envisagée (décisions à arbitrer — voir §03 et §02)

| Brique | Option cible | Souveraineté | Note |
|---|---|---|---|
| Transport | **LiveKit Agents** (Apache-2.0) | self-host possible | déjà choisi dans le dépôt |
| VAD | **Silero VAD** | open-source, CPU | gate du pipeline |
| Turn detection | LiveKit Turn Detector v1-mini (CPU local) | self-host | `[à câbler]` |
| STT | **Voxtral** (Mistral, FR natif) realtime | API EU / open-weights | clé API bloquante |
| LLM | **Mistral** (ex. `mistral-large` / `ministral-8b`) | API EU / open-weights | clé API bloquante |
| TTS | **Voxtral TTS** (API) **ou** **Kyutai TTS 1.6B** (open-weights, FR, self-host) | EU (Paris) | arbitrage licence (voir §03) |

## 9. Jalons (proposition)

- **J0 — Cadrage R&D** *(cette session)* : cahier des charges, veille sourcée, registre blocages, algorigrammes, catalogue skills, page Notion. ✅
- **J1 — Déblocage credentials** : obtenir `MISTRAL_API_KEY` + `LIVEKIT_*` (action humaine Davy).
- **J2 — Round-trip DB réel** : test d'intégration MariaDB *opt-in* (hors CI 0-dépendance).
- **J3 — Adaptateurs STT/LLM/TTS** : implémenter les `Protocol` de `runtime.py` (mock + 1 test live opt-in).
- **J4 — Câblage LiveKit** : `LiveKitRoomOut.play` + `LiveKitAudioBridge.start` + `main.run`.
- **J5 — Premier test vocal end-to-end** avec Davy (mesure latence/qualité FR/turn-taking).
- **J6 — Skills v1** : catalogue + garde-fous + évaluation.
- **J7 — Conformité** : mention IA, consentement, audit durci, (AIPD si applicable).

## 10. Critères d'acceptation (V1)

- [ ] Davy parle → VindIA répond en voix FR, en < 1 s perçue, sans larsen.
- [ ] Barge-in fonctionnel (couper le TTS quand Davy reprend la parole).
- [ ] Mention « vous parlez à une IA » + consentement explicite tracés.
- [ ] Audit append-only vérifiable (chaînage/immuabilité).
- [ ] Au moins 1 skill métier déclenchée par la voix, avec sortie validée.
- [ ] Aucun secret en clair dans le dépôt ; données traitées en UE.

## 11. Risques majeurs (synthèse — détail en §02)

1. **Credentials non fournis** (Mistral + LiveKit) → bloque tout test vocal réel. *Sévérité : critique.*
2. **Budget latence** non tenu (LLM = ~70 % de la latence) → UX dégradée. *Sévérité : élevée.*
3. **Licences TTS open-weights** (Voxtral TTS = CC-BY-NC ; XTTS = non-commercial) → usage commercial restreint. *Sévérité : moyenne.*
4. **Barge-in / AEC** non fiables hors casque → faux déclenchements. *Sévérité : moyenne.*
5. **Conformité** AI Act art. 50 (échéance 2026-08-02) + AIPD. *Sévérité : moyenne-élevée.*
