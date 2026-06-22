# Registre des blocages — VindIA R&D

> Pierre angulaire du projet : « commence par la préparation et les blocages potentiels » +
> « chaque session sert à récupérer un maximum d'informations pour répondre aux blocages ».
> Sévérité : 🔴 critique · 🟠 élevée · 🟡 moyenne · 🟢 faible. Statut : OUVERT / EN COURS / LEVÉ.

## Synthèse

| ID | Blocage | Sévérité | Resp. | Statut |
|---|---|---|---|---|
| B-001 | Credentials Mistral + LiveKit non fournis | 🔴 | Davy / Claude VPS | EN COURS (délégué Claude VPS, 2026-06-22) |
| B-002 | Budget de latence E2E à tenir (< 700 ms) | 🟠 | Claude | OUVERT (recherche faite) |
| B-003 | Licences TTS open-weights (usage commercial) | 🟡 | Davy/Claude | OUVERT (recherche faite) |
| B-004 | Barge-in / AEC fiable hors casque | 🟡 | Claude | OUVERT (recherche faite) |
| B-005 | Conformité AI Act art. 50 (éch. 2026-08-02) + AIPD | 🟠 | Davy/Claude | OUVERT (recherche faite) |
| B-006 | Diarisation → identité sans biométrie (art. 9) | 🟡 | Claude | OUVERT (cadré) |
| B-007 | Hallucinations LLM / fiabilité des skills | 🟡 | Claude | OUVERT (recherche faite) |
| B-008 | Mémoire de l'agent (context rot, drift) | 🟡 | Claude | OUVERT (recherche faite) |
| B-009 | Round-trip DB réel non testé (CI 0-dépendance) | 🟢 | Claude | OUVERT |

---

## B-001 — Credentials Mistral + LiveKit 🔴 CRITIQUE
**Description** : sans `MISTRAL_API_KEY` et `LIVEKIT_URL/API_KEY/API_SECRET`, impossible de câbler
STT/LLM/TTS réels ni le transport audio → **aucun test vocal end-to-end possible**. Déjà signalé
dans `docs/REPRISE-PC.md`.
**Impact** : bloque J3 (adaptateurs live), J4 (câblage LiveKit), J5 (1er test vocal).
**Piste de levée** :
- Mistral **La Plateforme** (`api.mistral.ai`) : hébergement **EU par défaut (Paris)**, données API
  non utilisées pour l'entraînement, rétention logs 30 j, DPA dispo → cohérent souveraineté.
  [WAIMAKERS GDPR Guide Mistral](https://www.waimakers.com/en/resources/gdpr-compliance/mistral-ai) ·
  [Mistral data storage FAQ](https://help.mistral.ai/en/articles/347629-where-do-you-store-my-data-or-my-organization-s-data)
- LiveKit : self-host possible (Apache-2.0) ou LiveKit Cloud. [github.com/livekit/agents](https://github.com/livekit/agents)
**Action attendue** : Davy fournit les secrets dans `server/.env` (jamais committé).
**Mise à jour 2026-06-22** : mission **déléguée à Claude VPS** (renseignement `server/.env` +
câblage adaptateurs STT/LLM/TTS + LiveKit, côté working copy VPS `/root/vindia-work`).
**Coordination** : pour éviter les conflits, l'instance VPS travaille le **code** (`shared/agent/…`) ;
cette instance reste sur la **R&D/doc/Notion/suivi** (`docs/RnD/…`) et ne touche pas `shared/agent/`
sans accord. Reconverger les branches avant merge.

## B-002 — Budget de latence E2E 🟠
**Description** : viser une latence perçue conversationnelle. Référence humaine : gap médian
**~200 ms** ([Stivers et al. 2009, PNAS](https://pubmed.ncbi.nlm.nih.gov/19553212/)). Seuil UX
« naturel » < 300–500 ms ; la plupart des agents réels sont à 800–1500 ms.
**Cause racine documentée** : le **LLM (TTFT) est le principal goulot** (~70 % de la latence en
pipeline non optimisé) — [Retell AI](https://www.retellai.com/blog/how-real-time-voice-ai-works-stt-llm-tts).
**Pistes de levée (sourcées)** :
- Streaming bout-en-bout obligatoire (STT partiels → LLM tokens → TTS chunks).
- LLM rapide : **Mistral Small 4** ~174 tok/s, TTFT 0,68–0,85 s, EU, tool-calling
  ([Artificial Analysis](https://artificialanalysis.ai/models/mistral-small-4)).
- Turn detection modèle plutôt que VAD seul : LiveKit Turn Detector v1 → 295 ms de « dead air »
  @10 % faux-coupures vs 1000 ms pour VAD seul ([EOT-Bench](https://github.com/livekit/eot-bench)).
- STT realtime Voxtral : délai optimal ~480 ms, sub-200 ms possible ([arXiv 2602.11298](https://arxiv.org/abs/2602.11298)).
- TTS streaming : 70–220 ms 1er audio (Voxtral TTS 70 ms modèle ; Kyutai ~200 ms TTFA).
**Reste à faire** : mesurer en conditions réelles dès J5 ; instrumenter P50/P95.

## B-003 — Licences TTS open-weights 🟡
**Description** : plusieurs TTS FR de qualité ont des licences **non commerciales** en self-host.
**Faits (sourcés)** :
- **Voxtral TTS** poids = **CC BY-NC 4.0** (non commercial) ; usage commercial **via API Mistral** ($0,016/1000 car.). [mistral.ai/news/voxtral-tts](https://mistral.ai/news/voxtral-tts/)
- **Coqui XTTS v2** = **CPML non commercial**, société fermée (jan. 2024) → pas de licence commerciale achetable. [github.com/idiap/coqui-ai-TTS](https://github.com/idiap/coqui-ai-TTS)
- **Piper** fork actif = **GPL-3.0** (copyleft) ; repo MIT original archivé oct. 2025. [OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl)
- **Kyutai TTS 1.6B** = **CC-BY 4.0** (code MIT/Apache), FR mesuré (WER 3,29 %), self-host GPU. [hf.co/kyutai/tts-1.6b-en_fr](https://huggingface.co/kyutai/tts-1.6b-en_fr)
- **Kyutai Pocket TTS** = **MIT**, FR, **CPU only**. [github.com/kyutai-labs/pocket-tts](https://github.com/kyutai-labs/pocket-tts)
- **Kokoro 82M** = **Apache 2.0**, FR, léger (auteur non-EU). [hf.co/hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M)
**Décision à prendre** : si usage commercial self-host → **Kyutai (MIT/CC-BY)** ou Kokoro (Apache) ;
si API acceptable → **Voxtral TTS** (le plus simple, EU). À arbitrer selon modèle économique + GPU.

## B-004 — Barge-in / AEC fiable 🟡
**Description** : couper le TTS quand l'utilisateur reprend la parole, sans faux déclenchements.
**Faits (sourcés)** :
- VAD seul = **51 % de faux barge-ins** rejetables ; LiveKit Adaptive Interruption détecte les vrais
  barge-ins plus vite dans 64 % des cas. [LiveKit](https://livekit.com/blog/adaptive-interruption-handling)
- Benchmark full-duplex : faux barge-in LiveKit 33,4 % vs FireRedChat 10,2 % ([arXiv 2509.06502](https://arxiv.org/abs/2509.06502)).
- Sans haut-parleur isolé, l'audio TTS rentre dans le micro → **AEC** nécessaire (double-talk = pb dur). [Switchboard/AEC3](https://switchboard.audio/hub/how-webrtc-aec3-works/)
**Atténuation V1** : **casques + half-duplex** (`HalfDuplexGate` déjà dans le dépôt) → supprime le larsen.
**Limite connue** : barge-in **adaptatif self-host** non dispo chez LiveKit (cloud-only, [issue #6033](https://github.com/livekit/agents/issues/6033)) → fallback VAD en self-host.

## B-005 — Conformité AI Act art. 50 + AIPD 🟠
**Description** : obligations légales avant mise en service.
**Faits (sourcés)** :
- **AI Act art. 50** : informer l'utilisateur qu'il **parle à une IA**, au 1er contact, clairement.
  Application **2 août 2026**. Sanctions jusqu'à 15 M€ / 3 % CA. [EUR-Lex 2024/1689](https://eur-lex.europa.eu/eli/reg/2024/1689/oj?locale=fr) · [art. 50](https://artificialintelligenceact.eu/article/50/)
- **art. 5(1)(f)** : reconnaissance d'émotions interdite au travail/éducation (depuis 2 fév. 2025).
- **AIPD probablement requise** pour assistant vocal (EDPB 02/2021). [EDPB Guidelines 02/2021](https://www.edpb.europa.eu/system/files/2022-02/edpb_guidelines_202102_on_vva_v2.0_adopted_fr.pdf)
**Action** : intégrer la mention IA + consentement dès J7 ; cadrer une AIPD ; **ne pas** faire de
reconnaissance d'émotions. `[INCERTAIN]` classification précise risque limité vs Annexe III (dépend du cas d'usage).

## B-006 — Diarisation sans biométrie 🟡
**Description** : séparer les locuteurs sans tomber sous l'art. 9 RGPD (biométrie).
**Cadrage (sourcé)** : la **diarisation pure** (labels « Locuteur A/B » sans identification unique)
n'est pas en soi un traitement biométrique art. 9 ; c'est **la finalité d'identification unique** qui
déclenche ce régime. Prudence sur les empreintes vocales intermédiaires. [EDPB 02/2021](https://www.edpb.europa.eu/system/files/2021-07/edpb_guidelines_202102_on_vva_v2.0_adopted_en.pdf)
**Décision dépôt (déjà prise)** : `speaker_id` = **label de diarisation** résolu vers `member_id`,
**jamais** utilisé comme identité → conforme à l'orientation.
**Note technique** : Voxtral **realtime ≠ diarisation** ; la diarisation est dispo en **batch**
(Voxtral Transcribe 2). DER réel multi-locuteurs 11–18 % ([arXiv 2509.26177](https://arxiv.org/html/2509.26177v1)).

## B-007 — Hallucinations LLM / fiabilité skills 🟡
**Description** : éviter réponses fabriquées et exécutions d'outils erronées.
**Pistes (sourcées)** :
- **RAG grounding** : −42 à −68 % d'hallucinations ; abstention « je ne sais pas » sous incertitude
  ([conformal abstention, arXiv 2405.01563](https://arxiv.org/pdf/2405.01563)).
- **Structured Outputs / contrainte de schéma** : 100 % de conformité schéma vs <40 % sans ([OpenAI, août 2024](https://openai.com/index/introducing-structured-outputs-in-the-api/)).
- **Guardrails** : NeMo Guardrails (rails entrée/dialogue/exécution/sortie, [EMNLP 2023](https://aclanthology.org/2023.emnlp-demo.40/)) + Guardrails AI (validators, reask).
- ⚠️ **Sécurité texte ≠ sécurité tool-call** : prévoir des garde-fous **sur l'exécution des skills** ([arXiv 2602.16943](https://arxiv.org/pdf/2602.16943)).

## B-008 — Mémoire de l'agent 🟡
**Description** : mémoire court/long terme fiable, sans dérive.
**Faits (sourcés)** :
- **« Lost in the middle »** : −30 % de précision quand l'info clé est au milieu d'un long contexte ([TACL 2024](https://aclanthology.org/2024.tacl-1.9.pdf)).
- **Context rot** mesuré sur 18 modèles ([Chroma/Morph](https://www.morphllm.com/context-rot)).
- Hallucinations **dans les systèmes de mémoire** (fabrication/conflits/omissions) — [HaluMem](https://arxiv.org/abs/2511.03506).
- Risques de **mémoire auto-modifiable** : drift, injection, croissance non contrôlée ([SSGM, arXiv 2603.11768](https://arxiv.org/html/2603.11768v1)).
**Orientation V1** : mémoire de **session** (court terme) d'abord ; long terme (profil/épisodique) en V2,
avec TTL et garde-fous.

## B-009 — Round-trip DB réel 🟢
**Description** : la CI est **0-dépendance** ; le DAO MariaDB n'a pas de test d'intégration live.
**Piste** : test d'intégration *opt-in* gardé par variable d'env (ne casse pas la CI), `pip install pymysql`,
`DB_DSN` depuis `server/.env`. (Déjà listé dans `docs/REPRISE-PC.md`.)
