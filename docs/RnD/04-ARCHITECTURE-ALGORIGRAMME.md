# Modèle complet — Architecture & algorigrammes (VindIA)

> Diagrammes en **Mermaid** (rendus nativement par GitHub et Notion). Modèle cible « complet avec
> visuel et algorigramme » demandé. Toutes les briques renvoient à la veille ([`03`](./03-VEILLE-SOURCEE.md)).

## 1. Architecture système (vue d'ensemble)

```mermaid
flowchart TB
    subgraph User["👤 Utilisateur (casque, half-duplex)"]
        MIC[Micro]
        SPK[Écouteurs]
    end

    subgraph Edge["Transport temps réel"]
        LK["LiveKit Room (WebRTC / Opus FEC)"]
    end

    subgraph Agent["🤖 Runtime VindIA (worker stateful par session)"]
        VAD["VAD Silero<br/>(gate, <1ms/chunk)"]
        TURN["Turn Detector v1-mini<br/>(audio+sémantique, CPU)"]
        STT["STT Voxtral realtime<br/>(streaming, ~480ms)"]
        LLM["LLM Mistral Small 4<br/>(tool-calling, TTFT~0.7s)"]
        SKILLS["Catalogue de skills<br/>(MCP / function-calling)"]
        GUARD["Garde-fous<br/>(schéma, grounding, abstention)"]
        TTS["TTS Voxtral / Kyutai<br/>(streaming, ~70-200ms)"]
        GATE["HalfDuplexGate<br/>(anti-larsen)"]
    end

    subgraph Gov["Souveraineté & conformité"]
        CONS["Consentement + mention IA<br/>(AI Act art.50)"]
        RESOLVE["Résolveur diarisation→member_id<br/>(jamais biométrie)"]
        AUDIT["Audit append-only<br/>(ALCOA+, WORM/hash-chain)"]
        DB["MariaDB EU (localhost)<br/>CHAR(36)"]
    end

    MIC --> LK --> VAD --> TURN --> STT --> GUARD --> LLM
    LLM <--> SKILLS
    LLM --> GUARD2["Garde-fous sortie"] --> TTS --> GATE --> LK --> SPK
    GATE -. suspend capture pendant TTS .-> VAD
    CONS -. gate .-> STT
    STT --> RESOLVE
    LLM --> AUDIT
    RESOLVE --> DB
    AUDIT --> DB
```

## 2. Algorigramme — boucle conversationnelle (un tour)

```mermaid
flowchart TD
    A([Début session]) --> B{Consentement<br/>+ mention IA ?}
    B -- non --> Z([Refus : pas de traitement])
    B -- oui --> C[Écoute micro via LiveKit]
    C --> D{VAD : voix détectée ?}
    D -- non --> C
    D -- oui --> E[Bufferiser segment + STT streaming]
    E --> F{Turn Detector :<br/>fin de tour ?}
    F -- non --> E
    F -- oui --> G[Transcription finalisée]
    G --> H[LLM Mistral + contexte session]
    H --> I{Besoin d'une skill ?<br/>tool_use ?}
    I -- oui --> J[Valider args = schéma JSON]
    J --> K{Args valides ?}
    K -- non --> L[REASK / corriger] --> H
    K -- oui --> M[Exécuter skill + garde-fou exécution]
    M --> N[Résultat outil → contexte]
    N --> H
    I -- non --> O{Réponse groundée<br/>+ confiance OK ?}
    O -- non --> P[Abstention : « je ne sais pas »]
    O -- oui --> Q[Texte de réponse]
    P --> Q
    Q --> R[TTS streaming]
    R --> S[HalfDuplexGate : suspendre capture]
    S --> T[Diffuser audio dans la room]
    T --> U[Journaliser tour : audit append-only]
    U --> V{Barge-in détecté<br/>pendant TTS ?}
    V -- oui --> W[Couper TTS < 200ms] --> C
    V -- non --> X{Fin de session ?}
    X -- non --> C
    X -- oui --> Y([Fin])
```

## 3. Machine à états — tour de parole & barge-in

```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> LISTENING : VAD = voix
    LISTENING --> LISTENING : turn non terminé
    LISTENING --> THINKING : Turn Detector = fin de tour
    THINKING --> THINKING : tool_use (skill) en boucle
    THINKING --> SPEAKING : réponse prête → TTS
    SPEAKING --> LISTENING : barge-in (couper TTS <200ms)
    SPEAKING --> IDLE : fin de réponse
    LISTENING --> IDLE : silence prolongé (user_away_timeout)
```

## 4. Flux de conformité (données & traçabilité)

```mermaid
flowchart LR
    U[Voix utilisateur] --> CONS{Consentement<br/>recueilli ?}
    CONS -- non --> STOP[Aucun traitement]
    CONS -- oui --> MIN[Minimisation : pas de stockage audio brut au-delà de l'utile]
    MIN --> PROC[Traitement EU<br/>Mistral La Plateforme / self-host]
    PROC --> DIAR[Diarisation = labels A/B]
    DIAR --> RES[Résolution → member_id applicatif]
    RES --> NOBIO[[Pas d'empreinte vocale d'identification — hors art.9]]
    PROC --> LOG[Audit append-only ALCOA+]
    LOG --> RIGHTS[Droits RGPD : accès / effacement / opposition]
```

## 5. Décomposition du budget de latence (cible)

```mermaid
flowchart LR
    A["Fin de parole"] --> B["Turn detection<br/>~150-300ms"]
    B --> C["STT (déjà streamé)<br/>~50-150ms"]
    C --> D["LLM TTFT<br/>~100-300ms ⚠️ goulot"]
    D --> E["TTS 1er audio<br/>~70-200ms"]
    E --> F["Réseau<br/>~30-80ms"]
    F --> G(["1er son agent<br/>cible < 700ms"])
```

> Réf. humaine ~200 ms ; cible industrie sub-500 ms. Le **LLM TTFT** domine → privilégier un modèle
> rapide (Mistral Small 4) + streaming partout. Sources : voir [`03` §6](./03-VEILLE-SOURCEE.md).

## 6. Mapping briques → code existant du dépôt

| Brique | Fichier dépôt | État |
|---|---|---|
| Session/consentement | `shared/agent/session.py` | ✅ posé |
| VAD | `shared/agent/audio/vad.py` (`VoiceSegmenter`) | ✅ testé (stdlib) |
| Transport LiveKit | `shared/agent/audio/livekit_io.py` | 🟠 squelettes TODO |
| Orchestration tour | `shared/agent/router.py` + `main.py` | 🟠 câblage partiel |
| Runtime STT→LLM→TTS | `shared/agent/runtime.py` (`Protocol`) | ✅ contrats / 🟠 adaptateurs |
| Résolveur diarisation | `shared/agent/store.py` (`make_member_resolver`) | 🟠 à brancher |
| Audit | `shared/agent/store.py` (`make_audit_sink`) | 🟠 à brancher |
| Persistance | `db/01-schema.sql` (MariaDB CHAR(36)) | ✅ validé |
