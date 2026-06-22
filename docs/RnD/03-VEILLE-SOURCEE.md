# Veille R&D sourcée — Agents vocaux conversationnels (VindIA)

> **Politique 0 hallucination.** Toute affirmation renvoie à une source primaire ou reconnue.
> Les marqueurs `[INCERTAIN]` / `[NON TROUVÉ]` sont conservés tels quels.
> **Méthodologie & limite** : recherche en fan-out (WebSearch + WebFetch), ~10 angles, le 2026-06-22.
> Plusieurs domaines officiels (mistral.ai, docs.mistral.ai, docs.livekit.io, huggingface.co) ont
> renvoyé des erreurs **403** au fetch direct ; les faits correspondants proviennent alors des
> **extraits indexés** par le moteur et de sources secondaires reconnues, et sont signalés quand le
> doute subsiste. Les chiffres de prix/latence sont volatils → à re-vérifier avant décision.

## Table des matières
1. Voxtral (STT / compréhension / realtime / TTS)
2. Mistral LLM pour la conversation temps réel
3. LiveKit Agents (orchestration du pipeline vocal)
4. VAD & détection de tour de parole (Silero, Turn Detector)
5. TTS souverains FR (Kyutai, Piper, Coqui, Voxtral, Kokoro)
6. Budget de latence & turn-taking (références humaines, full/half-duplex)
7. Robustesse : AEC/echo, diarisation, WebRTC, observabilité
8. Hallucinations & fiabilité (grounding, structured outputs, guardrails)
9. Mémoire de l'agent (court/long terme, échecs)
10. Skills / compétences (tool-calling, MCP, Agent Skills, benchmarks)
11. Conformité EU (RGPD, AI Act, ALCOA+, NIS2, souveraineté)

---

## 1. Voxtral (Mistral) — famille de modèles vocaux

Voxtral n'est **pas** un simple ASR : c'est une famille de **compréhension audio** multimodale.

| Génération | Modèle | Params | Rôle | Licence |
|---|---|---|---|---|
| G1 (15 juil. 2025) | Voxtral-Small-24B-2507 | 24B | Compréhension audio avancée | Apache 2.0 |
| G1 | Voxtral-Mini-3B-2507 | 3B | Edge/local | Apache 2.0 |
| G2 (4 fév. 2026) | Voxtral Mini Transcribe V2 (batch) | 4B | ASR batch **+ diarisation** | `[INCERTAIN open-weights]` |
| G2 | Voxtral-Mini-4B-Realtime-2602 (streaming) | 4B | ASR temps réel | Apache 2.0 |
| G3 (26 mars 2026) | Voxtral-4B-TTS-2603 | 4B | TTS streaming + clonage voix | CC BY-NC 4.0 |

**Langues** : FR nativement supporté (STT : 13 langues ; TTS : 9 langues).
**Performance FR (FLEURS)** : Voxtral-Mini-3B WER **5,75 %** (vs Whisper large-v3 7,15 %).
**Realtime** : architecture nativement streaming, délai configurable **240 ms→2,4 s** (multiples de
80 ms), point optimal **~480 ms** (≈ qualité offline) ; sub-200 ms possible selon réglage.
**Diarisation** : disponible en **batch** (Transcribe 2, labels Speaker 1/2, timestamps mot à mot,
jusqu'à 3 h) ; **non disponible** sur le modèle realtime streaming.
**Tool/function-calling depuis la voix** : supporté par Voxtral Small/Mini 2507 (une passe).
**Tarifs API (indicatifs)** : Transcribe batch $0,003/min ; Realtime $0,006/min ; TTS $0,016/1000 car.
`[NON TROUVÉ : confirmation prix Voxtral TTS/Realtime sur La Plateforme]`.

Sources : [Voxtral](https://mistral.ai/news/voxtral/) · [Transcribe 2](https://mistral.ai/news/voxtral-transcribe-2/) · [Voxtral TTS](https://mistral.ai/news/voxtral-tts/) · [arXiv 2507.13264](https://arxiv.org/abs/2507.13264) · [arXiv 2602.11298 (realtime)](https://arxiv.org/abs/2602.11298) · [HF Realtime](https://huggingface.co/mistralai/Voxtral-Mini-4B-Realtime-2602) · [HF TTS](https://huggingface.co/mistralai/Voxtral-4B-TTS-2603) · [Simon Willison](https://simonwillison.net/2026/Feb/4/voxtral-2/)

---

## 2. Mistral LLM — conversation temps réel (2025-2026)

| Modèle | API ID | Contexte | Tool-calling | TTFT | Débit | Prix in/out /1M |
|---|---|---|---|---|---|---|
| **Small 4** | `mistral-small-2603` | 256K | ✅ parallèle | **0,68–0,85 s** | **174,5 tok/s** | $0,15 / $0,60 |
| Large 3 | `mistral-large-2512` | 256K | ✅ parallèle | 1,17 s | 50,7 tok/s | $2,00 / $6,00 |
| Medium 3.5 | `mistral-medium-3-5` `[ID exact INCERTAIN]` | 256K | ✅ parallèle | 2,14 s | 141 tok/s | $1,50 / $7,50 |
| Ministral 8B | `ministral-8b-2512` | 256K | ✅ | `[NON TROUVÉ]` | `[NON TROUVÉ]` | $0,10 / $0,10 |
| Ministral 3B | `ministral-3b-2512` | 128K* | ✅ | `[NON TROUVÉ]` | `[NON TROUVÉ]` | $0,04 / $0,04 |

\* contexte Ministral 3B : conflit 128K (docs initiales) vs 256K (agrégateurs). Prix `[INCERTAIN]`
(agrégateurs tiers ; page officielle injoignable).

**Recommandation temps réel (texte)** : **Mistral Small 4** = meilleur compromis vitesse/coût/
tool-calling/contexte, **hébergé EU**.
**Souveraineté** : La Plateforme `api.mistral.ai` = **EU par défaut (Paris)**, données API non
utilisées pour l'entraînement, rétention 30 j, DPA dispo. Aussi Azure (FR/DE/EU regions, `[SKU global INCERTAIN]`),
AWS Bedrock Frankfurt. **Mistral Compute** : infra souveraine EU (France/Suède) en montée 2026-2027.
**Agents API** (mai 2025) : état multi-tours persistant + outils intégrés (websearch, code_interpreter…).

Sources : [Mistral 3](https://mistral.ai/news/mistral-3/) · [Small 4](https://mistral.ai/news/mistral-small-4/) · [Artificial Analysis Small 4](https://artificialanalysis.ai/models/mistral-small-4) · [La Plateforme](https://mistral.ai/news/la-plateforme/) · [Mistral Compute](https://mistral.ai/news/mistral-compute/) · [AWS Bedrock Large 3](https://aws.amazon.com/about-aws/whats-new/2025/12/mistral-large-3-ministral-3-family-available-amazon-bedrock/) · [GDPR guide](https://www.waimakers.com/en/resources/gdpr-compliance/mistral-ai)

---

## 3. LiveKit Agents — orchestration du pipeline vocal

Framework open-source (**Apache-2.0**), Python/Node. v1.0 avr. 2025 ; **v1.6.2 (19 juin 2026)**.
Abstraction centrale : **`AgentSession`** (orchestre input → VAD → STT → LLM → TTS → output, événements
d'observabilité, `max_tool_steps`, `aec_warmup_duration`, etc.).

- **Pipeline cascade** streaming par défaut ; **S2S** (speech-to-speech) aussi supporté.
- **Plugins** (50+) : `mistralai`, `anthropic`, `openai`, `google`, `elevenlabs`, `deepgram`,
  `silero`, `turn-detector`, `mcp`… (`pip install "livekit-agents[mistralai]"`).
- **Pipeline nodes** (`stt_node`, `llm_node`, `tts_node`, `on_enter/on_exit`) pour personnaliser chaque étape.
- **Plugin `livekit-plugins-mistralai` (v1.6.2)** : pipeline **100 % Mistral** possible (cas d'usage
  **EU** explicitement visé, [issue #5247](https://github.com/livekit/agents/issues/5247)) :
  - STT : `voxtral-mini-latest` (batch) / `voxtral-mini-transcribe-realtime-2602` (realtime, **requiert Silero VAD**, PCM16 16 kHz mono) ;
  - LLM : `ministral-8b-latest` par défaut, configurable (`mistral-large-latest`…) ;
  - TTS : `voxtral-mini-tts-2603` (voix intégrées + clonage zero-shot).

Sources : [github.com/livekit/agents](https://github.com/livekit/agents) · [PyPI livekit-agents](https://pypi.org/project/livekit-agents/) · [PyPI mistralai plugin](https://pypi.org/project/livekit-plugins-mistralai/) · [agent_session.py](https://github.com/livekit/agents/blob/main/livekit-agents/livekit/agents/voice/agent_session.py) · [issue #4754 (Voxtral realtime)](https://github.com/livekit/agents/issues/4754)

---

## 4. VAD & détection de tour de parole

**Silero VAD** (open-source) : modèle ~2 MB (V5), **< 1 ms / chunk de 30 ms sur 1 thread CPU**
(README officiel) ; fenêtres fixes 32 ms (512 samples @16 kHz) ; stateful (streaming natif) ;
nettement supérieur à WebRTC VAD en milieu bruité (TPR 87,7 % @5 % FA vs ~50 %).

**LiveKit Turn Detector** : a évolué d'un modèle basé **transcript** (SmolLM2-135M) vers **v1**
(fusion **audio + sémantique**, backbone Qwen2.5-0.5B distillé) → écoute l'audio brut, supprime la
latence de transcription. Variantes : `v1` (cloud) et **`v1-mini` (CPU local, self-host)**.
Le plugin `livekit-plugins-turn-detector` est **déprécié** (juin 2026) au profit de
`livekit.agents.inference.TurnDetector` intégré.

**EOT-Bench (anglais)** — « dead air » à budget de 10 % de faux-coupures :
LiveKit v1 **295 ms** · Deepgram Flux 548 ms · **VAD seul 1000 ms**. → le modèle de turn detection
réduit fortement le silence ressenti.
`[INCERTAIN]` tailles/latences exactes du turn-detector (66 MB/281 MB, 15-160 ms) : sources
secondaires, docs LiveKit en 403.

Sources : [Silero VAD](https://github.com/snakers4/silero-vad) · [EOT-Bench](https://github.com/livekit/eot-bench) · [Solving end-of-turn detection](https://livekit.com/blog/solving-end-of-turn-detection) · [HF turn-detector](https://huggingface.co/livekit/turn-detector)

---

## 5. TTS souverains FR — comparatif

| Système | Open weights | Licence | Qualité FR | Latence | Hébergement | Souveraineté EU |
|---|---|---|---|---|---|---|
| **Kyutai TTS 1.6B** | ✅ | CC-BY 4.0 | WER 3,29 %, SIM 78,7 % | ~200 ms TTFA | GPU (L40S prod) | ✅ Paris |
| **Kyutai Pocket TTS** | ✅ | **MIT** | voix « estelle » `[INCERTAIN]` | ~200 ms TTFA | **CPU** (2 cœurs) | ✅ Paris |
| **Voxtral TTS** | ✅ | **CC BY-NC** | WER 3,22 %, 68,4 % vs ElevenLabs | 70 ms (modèle) | GPU ≥16 GB / API | ✅ Paris |
| Piper (OHF) | ✅ | **GPL-3.0** | medium max | RTF 0,04× | CPU/ONNX | neutre (US OHF) |
| Coqui XTTS v2 | ✅ | CPML (NC) | bonne, clonage | <200 ms (GPU) | GPU ~8 GB | projet fermé |
| Kokoro 82M | ✅ | **Apache 2.0** | `[INCERTAIN FR]` | temps réel | CPU | non-EU (auteur anon.) |

**Lecture** : pour usage **commercial self-host** → **Kyutai** (MIT/CC-BY) ou Kokoro (Apache) ;
pour **API simple EU** → **Voxtral TTS** (poids NC mais usage commercial via API). Cf. blocage **B-003**.

Sources : [Kyutai TTS](https://huggingface.co/kyutai/tts-1.6b-en_fr) · [Pocket TTS](https://github.com/kyutai-labs/pocket-tts) · [Voxtral TTS](https://mistral.ai/news/voxtral-tts/) · [Piper OHF](https://github.com/OHF-Voice/piper1-gpl) · [Coqui idiap](https://github.com/idiap/coqui-ai-TTS) · [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M)

---

## 6. Budget de latence & turn-taking

**Référence humaine** : gap médian entre tours **~200 ms** (modes 0–200 ms), universel inter-langues
([Stivers et al. 2009, PNAS](https://pubmed.ncbi.nlm.nih.gov/19553212/)). Les humains **projettent**
la fin de tour (production > 600 ms mais transition ~200 ms — [Levinson & Torreira 2015](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4464110/)).

**Décomposition (pipeline cascade, optimisé)** : VAD/endpointing 150–300 ms + STT 50–150 ms +
**LLM TTFT 100–300 ms (goulot principal, ~70 %)** + TTS 50–150 ms + réseau 30–80 ms ≈ **400–800 ms**
optimisé ; 800–1500 ms en production typique. Cible industrie : **sub-500 ms** (excellent sub-300 ms).

**Half-duplex + barge-in** (dominant) vs **full-duplex** (émergent). Benchmark barge-in (T90 / faux
positifs) : Ten 90 ms/78,1 % · LiveKit 140 ms/33,4 % · FireRedChat 170 ms/10,2 % ([arXiv 2509.06502](https://arxiv.org/abs/2509.06502)).
Cibles industrie barge-in : succès > 96 %, faux < 2–5 %, coupure TTS < 200 ms.

Sources : [LiveKit latency](https://livekit.com/blog/understand-and-improve-agent-latency) · [Retell AI](https://www.retellai.com/blog/how-real-time-voice-ai-works-stt-llm-tts) · [Hamming AI](https://hamming.ai/resources/voice-ai-latency-whats-fast-whats-slow-how-to-fix-it)

---

## 7. Robustesse : AEC, diarisation, WebRTC, observabilité

- **AEC / echo** : si haut-parleur ouvert, le TTS revient au micro → faux barge-ins. WebRTC **AEC3**
  (blocs 4 ms, gestion du **double-talk** par cohérence) ; le double-talk reste le problème le plus dur.
  → V1 : **casques + half-duplex** suppriment le besoin d'AEC.
  [Switchboard AEC3](https://switchboard.audio/hub/how-webrtc-aec3-works/) · [ACM 10.1145/3448734.3450856](https://dl.acm.org/doi/fullHtml/10.1145/3448734.3450856)
- **Diarisation** : DER réel 10–18 % (jusqu'à >30 % en chevauchement/bruit) ; gap 2→3 locuteurs
  marqué (WDER 2,68 %→11,65 %). NVIDIA **Streaming Sortformer** (août 2025) pour le temps réel.
  [arXiv 2509.26177](https://arxiv.org/html/2509.26177v1) · [PMC11041969](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11041969/)
- **WebRTC** : UDP + **Opus FEC** (+20–30 % overhead) + **NetEQ** (jusqu'à ~15 % de perte gérée) ;
  RFC 8854. Contrainte clé : **session WebRTC stateful** → un worker dédié par session, **pas de
  serverless éphémère**. [RFC 8854](https://datatracker.ietf.org/doc/rfc8854/) · [LiveKit](https://livekit.com/blog/real-time-voice-agents-vs-model-apis)
- **Observabilité** : OpenTelemetry sur tout le pipeline ; LiveKit émet `EOUMetrics`/`LLMMetrics`/
  `TTSMetrics` (corréler par `speech_id`), export OTLP (Langfuse, SigNoz…). KPIs : WER < 5 %, MOS
  4,3–4,5, task completion > 90 %, P50 < 1,5 s / P95 < 3,5 s, false barge-in < 1,4 %.
  [LiveKit observability](https://livekit.com/products/agent-observability) · [Hamming AI metrics](https://hamming.ai/resources/voice-agent-evaluation-metrics-guide)

---

## 8. Hallucinations & fiabilité

- **RAG grounding** : −42 à −68 % d'hallucinations (jusqu'à −96 % avec RAG+RLHF+guardrails selon
  une étude). Réponse « non groundée » = hallucination. [arXiv 2505.04847](https://arxiv.org/html/2505.04847v2)
- **Abstention sous incertitude** : conformal abstention (« je ne sais pas » avec garanties),
  I-CALM, GRACE (RL grounding/abstention). [arXiv 2405.01563](https://arxiv.org/pdf/2405.01563)
- **Structured Outputs / décodage contraint** : **100 %** de conformité schéma (gpt-4o-2024-08-06)
  vs <40 % avant ; Pydantic/Zod. [OpenAI](https://openai.com/index/introducing-structured-outputs-in-the-api/)
- **Guardrails** : NeMo Guardrails (rails entrée/dialogue/retrieval/**exécution**/sortie, Colang,
  [EMNLP 2023](https://aclanthology.org/2023.emnlp-demo.40/)) ; Guardrails AI (validators + on-fail
  EXCEPTION/REASK/FIX/FILTER). [github](https://github.com/guardrails-ai/guardrails)
- ⚠️ **Sécurité texte ≠ sécurité tool-call** : l'alignement texte ne se transfère pas à l'usage
  d'outils → garde-fous **sur l'exécution des skills** requis. [arXiv 2602.16943](https://arxiv.org/pdf/2602.16943)
- **Patterns de fiabilité** : classification d'erreurs (transitoire vs persistant), backoff+jitter,
  circuit breaker, fallback de modèle, **HITL** sur actions à fort impact. 79 % des échecs agents ne
  sont **pas** des pannes d'infra (spécification 41,8 % + coordination 36,9 %).

---

## 9. Mémoire de l'agent

- **Taxonomie** : court terme = fenêtre de contexte (working memory) ; long terme = stores externes
  (sémantique/épisodique/procédurale). [Survey arXiv 2602.06052](https://arxiv.org/pdf/2602.06052)
- **Architectures** : **MemGPT/Letta** (hiérarchie type OS : main/recall/archival + auto-édition,
  [arXiv 2310.08560](https://arxiv.org/abs/2310.08560)) ; **LangGraph** (checkpointers par `thread_id`
  + store transversal) ; **LlamaIndex** (FIFO + flush vers long terme) ; **Mem0** (retrieval multi-
  signal, [arXiv 2504.19413](https://arxiv.org/abs/2504.19413)).
- **Échecs** : **« lost in the middle »** (−30 % au milieu du contexte, [TACL 2024](https://aclanthology.org/2024.tacl-1.9.pdf)) ;
  **context rot** (18 modèles, [Morph](https://www.morphllm.com/context-rot)) ; **hallucinations de
  mémoire** (fabrication/conflit/omission, [HaluMem](https://arxiv.org/abs/2511.03506)) ; **drift /
  injection / croissance** des mémoires auto-modifiables ([SSGM](https://arxiv.org/html/2603.11768v1)).
- **Orientation VindIA** : V1 = mémoire de **session** ; long terme (profil) en V2 avec **TTL** + garde-fous.

---

## 10. Skills / compétences

Trois paradigmes : prompt engineering → **tool/function-calling** → **skill engineering**.

- **Tool/function-calling** : tool = `name` + `description` + `input_schema` (JSON Schema 2020-12) ;
  `tool_choice` auto/any/tool ; boucle client tant que `stop_reason: tool_use`. [Anthropic tool use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use) · [OpenAI function calling](https://platform.openai.com/docs/guides/function-calling)
- **MCP** (« USB-C de l'IA », Anthropic, 25 nov. 2024, JSON-RPC 2.0) : Hosts/Clients/Servers ;
  primitives **Tools / Resources / Prompts** ; `tools/list` + `tools/call` ; transports **stdio** et
  **Streamable HTTP**. [modelcontextprotocol.io](https://modelcontextprotocol.io/docs/getting-started/intro) · [Anthropic](https://www.anthropic.com/news/model-context-protocol)
- **Agent Skills** (standard ouvert Anthropic, déc. 2025) : dossier + **`SKILL.md`** (front-matter
  YAML name/description + corps Markdown d'instructions, scripts, ressources), chargé dynamiquement,
  portable entre agents. ⚠️ étude : **26,1 %** des skills communautaires contiennent des
  vulnérabilités → gouvernance nécessaire. [Anthropic Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) · [docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) · [arXiv 2602.12430](https://arxiv.org/abs/2602.12430)
- **Benchmarks** : AgentBench, ToolLLM/ToolBench, GAIA, SWE-bench (capacité) ; **ReliabilityBench**
  (fiabilité sous stress, [arXiv 2601.06112](https://arxiv.org/pdf/2601.06112)). Détail : voir [`05-CATALOGUE-SKILLS.md`](./05-CATALOGUE-SKILLS.md).

---

## 11. Conformité EU (orientation — pas un avis juridique)

> Synthèse ; détail et niveaux de certitude dans le rapport conformité. Toute décision = validation juriste.

- **RGPD** : base légale art. 6 (contrat/intérêt légitime/consentement) ; **art. 9** (biométrie) **si
  identification vocale** → consentement explicite (évité en V1) ; **diarisation pure ≠ biométrie** ;
  **AIPD probablement requise** (EDPB 02/2021) ; minimisation (edge), durées proportionnées, droits des
  personnes. [CNIL Livre Blanc assistants vocaux](https://www.cnil.fr/fr/votre-ecoute-la-cnil-publie-son-livre-blanc-sur-les-assistants-vocaux) · [EDPB 02/2021](https://www.edpb.europa.eu/system/files/2022-02/edpb_guidelines_202102_on_vva_v2.0_adopted_fr.pdf)
- **EU AI Act (Règl. 2024/1689)** : agent conversationnel = **risque limité** a priori `[INCERTAIN
  selon cas d'usage / Annexe III]` ; **art. 50** = informer qu'on parle à une IA, **application 2 août
  2026** ; **art. 5(1)(f)** = reconnaissance d'émotions interdite au travail/éducation (depuis 2 fév.
  2025). [EUR-Lex 2024/1689](https://eur-lex.europa.eu/eli/reg/2024/1689/oj?locale=fr) · [calendrier](https://artificialintelligenceact.eu/implementation-timeline/)
- **ALCOA+** : cadre d'intégrité (origine pharma/GxP) **transposé par analogie** à l'audit log
  append-only (WORM, hash-chaining, séparation des droits). Applicabilité directe hors GxP **FAIBLE** ;
  s'articule avec l'**accountability** RGPD art. 5(2)/24. [Vaisala ALCOA++](https://www.vaisala.com/fr/blog/2024-11/integrite-des-donnees-et-principes-alcoa-dans-la-surveillance-continue-gxp)
- **NIS2 (Dir. 2022/2555)** : selon taille/secteur ; mesures art. 21 + notification 72 h ;
  **transposition FR non promulguée au 2026-06-22** (examen AN repoussé juil. 2026). [EUR-Lex 2022/2555](https://eur-lex.europa.eu/eli/dir/2022/2555) · [Sénat](https://www.senat.fr/rap/l24-393/l24-39314.html)
- **Souveraineté / transferts** : hébergement UE/EEE, DPA art. 28 sous-traitants, CCT (Déc. 2021/914)
  pour transferts hors UE, EU Cloud CoC, SecNumCloud/GAIA-X `[garanties en déploiement]`.
