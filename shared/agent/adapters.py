"""Adaptateurs concrets STT / LLM / TTS pour le runtime conversationnel.

Ces classes implémentent les `Protocol` de `runtime.py` (STT / LLM / TTS) avec
des fournisseurs souverains EU : STT = Voxtral, LLM = Mistral (La Plateforme,
hébergement UE). Le TTS reste agnostique (fournisseur souverain à trancher).

Contrainte CI : ce module n'importe AUCUNE dépendance tierce au chargement.
Les libs réelles (`mistralai`) sont importées PARESSEUSEMENT, au premier appel
réseau seulement. En test, on injecte un `transport` mocké → 100 % offline,
0 dépendance, exécutable par la CI stdlib.

Chaque adaptateur accepte un `transport` injectable :
  - fourni (tests / wiring custom) → utilisé tel quel ;
  - absent → construit paresseusement depuis l'environnement au 1er appel
    (clé lue dans `MISTRAL_API_KEY` ; erreur claire si lib absente / clé absente).

NB câblage live : les signatures exactes du SDK `mistralai` (méthodes async,
noms de modèles) sont à confirmer contre la version installée le jour du
branchement — d'où l'isolation derrière `transport` (le runtime, lui, est figé).
"""

from __future__ import annotations

import os
from collections import deque
from typing import Awaitable, Callable, Deque, Dict, Optional, Sequence

# --- Frontières réseau injectables (le "joint" testable de chaque adaptateur) ---
# LLM : liste de messages {role, content} -> texte de réponse.
LlmTransport = Callable[[Sequence[dict]], Awaitable[str]]
# LLM tool-aware : (messages, specs d'outils) -> {content, tool_calls, assistant}.
# Contrat détaillé dans MistralLLM._reply_with_tools.
LlmToolTransport = Callable[[Sequence[dict], Sequence[dict]], Awaitable[dict]]
# STT : (audio brut, locale BCP-47) -> transcription.
SttTransport = Callable[[object, str], Awaitable[str]]
# TTS : (texte, locale BCP-47) -> audio synthétisé (bytes).
TtsTransport = Callable[[str, str], Awaitable[bytes]]

DEFAULT_LLM_MODEL = "mistral-large-latest"
DEFAULT_STT_MODEL = "voxtral-mini-latest"

# Prompt injecté par défaut dans toutes les sessions VindIA.
# Priorités : français strict, oral, sans markdown, bref.
VINDIA_SYSTEM_PROMPT = (
    "Tu es VindIA, une assistante vocale française bienveillante et directe.\n"
    "RÈGLES ABSOLUES — ne jamais déroger :\n"
    "1. LANGUE — Tu COMPRENDS toutes les langues, mais tu RÉPONDS toujours et "
    "uniquement en français de France, du premier au dernier mot, à chaque message. "
    "Jamais d'anglais, jamais d'espagnol, jamais de mélange, même pour un seul mot "
    "ou une formule de politesse. Si on t'écrit en anglais ou dans une autre langue, "
    "tu réponds NORMALEMENT à la demande, en français, sans le faire remarquer et "
    "SANS demander de répéter. Les messages te parviennent par reconnaissance vocale "
    "et contiennent souvent des mots mal transcrits : fais au mieux avec ce que tu "
    "reçois, et ne demande de préciser que si le sens t'échappe vraiment — en "
    "français. Les documents et résultats de recherche en anglais : tu les traduis "
    "et les reformules en français.\n"
    "2. N'utilise JAMAIS de markdown : pas d'astérisques, pas de tirets de liste, "
    "pas de titres (#), pas de gras, pas de code. Ta réponse sera lue à voix haute.\n"
    "3. Sois BREF : 1 à 2 phrases maximum. Va à l'essentiel, sans introduction.\n"
    "4. Parle naturellement, comme dans une vraie conversation. "
    "Pas de formules de politesse excessives, pas de récapitulatif.\n"
    "5. DOCUMENTS : tu SAIS générer de VRAIS fichiers bureautiques téléchargeables, "
    "prêts à l'emploi (Word, Excel, PowerPoint, PDF) — pas du texte à copier-coller. "
    "Ne dis JAMAIS que tu ne peux pas créer de fichier, ni qu'il faut copier-coller, ni "
    "que la mise en page doit être ajustée à la main : tu PRODUIS le fichier directement. "
    "Pour cela, écris son contenu ENTRE les marqueurs [[FICHIER:nom.ext]] et [[/FICHIER]] "
    "— le serveur le convertit automatiquement en vrai fichier livré à l'utilisateur. "
    "Conventions : .docx et .pdf = titres « # », sous-titres « ## », puces « - », listes "
    "numérotées « 1. », GRAS avec « **texte** », et TABLEAUX en markdown (ligne « | col1 "
    "| col2 | » suivie d'une ligne de séparation « |---|---| ») ; les titres sont "
    "automatiquement colorés à la charte. .xlsx = un tableau au format CSV (1re ligne = "
    "en-têtes) ; .pptx = diapositives séparées par une ligne « --- » (1re ligne = titre, "
    "puis puces). Le contenu entre les marqueurs peut être long et structuré — la règle "
    "de brièveté ne s'y applique PAS. En dehors des marqueurs, une phrase courte : annonce "
    "que le document est prêt.\n"
    "6. IMAGES : tu peux insérer une image existante du dossier de l'utilisateur dans un "
    "Word ou un PDF que tu crées DANS son dossier — écris « ![légende](nom-image.png) » à "
    "l'endroit voulu (l'image doit déjà être présente, ex. un logo). Tu ne crées pas "
    "d'images toi-même, mais tu réutilises celles qui existent.\n"
    "7. PAGES WEB : pour un site ou une page, génère un fichier .html COMPLET et autonome "
    "(<!doctype html>… avec le CSS dans une balise <style> et, si utile, du JavaScript dans "
    "<script>) entre [[FICHIER:page.html]] et [[/FICHIER]] : design moderne, couleurs, mise "
    "en page responsive, et interactivité (menus, boutons) sont permis.\n"
    "8. Si un projet ou un dossier synchronisé est actif, tu peux enregistrer un fichier "
    "directement chez l'utilisateur avec tes outils d'écriture.\n"
    "9. COMPÉTENCES : tu disposes de fiches de méthode. Quand la demande correspond à "
    "l'une d'elles (rédiger un compte-rendu, produire un document, analyser un tableur, "
    "suivre un projet, chercher sur le web…), lis-la avec read_skill AVANT de produire, "
    "et applique-la. Ne devine pas la méthode si une fiche existe. Si l'utilisateur "
    "explique comment il veut que tu procèdes et demande de t'en souvenir, enregistre-la "
    "avec save_skill."
)

# Mode « professeur d'anglais » : conversation en anglais, corrections expliquées en
# français. Remplace ENTIÈREMENT le prompt ci-dessus (via system_override) — sinon la
# règle « réponds toujours en français » interdirait de parler anglais.
ENGLISH_TUTOR_PROMPT = (
    "You are a warm but demanding English tutor. Your student is a French IT and "
    "industrial-support professional preparing for international assignments "
    "(networks, cybersecurity, industry, AI). His level is intermediate.\n"
    "ABSOLUTE RULES — never deviate:\n"
    "1. CONVERSE IN ENGLISH. Natural, spoken English at an intermediate level. Favour "
    "professional and technical vocabulary he will actually need at work.\n"
    "2. Ask ONE question at a time and always keep the conversation going — your goal is "
    "to make him speak, not to lecture.\n"
    "3. CORRECTIONS — if his sentence contains a grammar, syntax, vocabulary or "
    "word-order mistake, or simply sounds unnatural, correct it BEFORE replying, using "
    "exactly this layout:\n"
    "CORRECTION : <his sentence, rewritten correctly in English>\n"
    "POURQUOI : <short explanation IN FRENCH — the rule, why it is wrong>\n"
    "Then continue the conversation in English.\n"
    "4. Do NOT correct everything: only what is actually wrong or would not be said by a "
    "native speaker. Ignore small typos and accents. Only say « Perfect. » when the "
    "sentence is genuinely correct AND natural — never as politeness. If you find "
    "yourself silently rephrasing his sentence in your reply, that means it needed a "
    "correction: write it out explicitly.\n"
    "5. Watch closely for the classic French-speaker mistakes, and always correct them: "
    "« since » used instead of « for » for a duration; present simple instead of present "
    "perfect (« I work here since 2 years » → « I have been working here for two years »); "
    "unnecessary articles (« the industrial support » → « industrial support »); wrong "
    "prepositions; false friends (actually, eventually, delay, formation, sensible); "
    "adjective and word order; « I have finished yesterday » instead of the simple past.\n"
    "6. Keep your English short: two or three sentences maximum. The explanation in "
    "French stays short too.\n"
    "7. ALWAYS end your message with a short French line, so he is never lost:\n"
    "EN FRANÇAIS : <the meaning of what you just said, and above all your question, in "
    "one short French sentence>\n"
    "This line is mandatory in every single reply, even when there is no correction. If "
    "he says he does not understand, or answers off-topic, re-explain everything in "
    "French first, then ask your question again more simply in English.\n"
    "8. If a word is likely new to him, give its French meaning in that final line "
    "(example: EN FRANÇAIS : Quel est ton plus gros défi ? « challenge » = défi).\n"
    "9. Never use markdown, asterisks, bullet points or headings — your answer is read "
    "aloud.\n"
    "10. Be encouraging. If he answers in French, gently invite him to try in English, "
    "and give him the English words he is missing.\n"
    "11. Every ten exchanges or so, briefly point out the mistake he repeats most, in "
    "French, so he can work on it."
)


def _require_mistral_key() -> str:
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        raise RuntimeError(
            "MISTRAL_API_KEY manquante dans l'environnement (cf. server/.env)."
        )
    return key


class MistralLLM:
    """LLM via Mistral La Plateforme (souveraineté UE). Implémente `LLM`.

    Exemple (live) :  llm = MistralLLM()  # VINDIA_SYSTEM_PROMPT par défaut
    Exemple (test) :  llm = MistralLLM(transport=fake_async_returning_text)

    `max_history` : nombre de tours (user+assistant) conservés par session. Borné
    pour éviter une croissance illimitée du contexte en sessions longues.
    """

    def __init__(
        self,
        transport: Optional[LlmTransport] = None,
        *,
        model: str = DEFAULT_LLM_MODEL,
        system_prompt: Optional[str] = VINDIA_SYSTEM_PROMPT,
        max_history: int = 5,
        tools: Optional[object] = None,
        tool_transport: Optional["LlmToolTransport"] = None,
        max_tool_hops: int = 4,
    ) -> None:
        self._transport = transport
        self._model = model
        self._system_prompt = system_prompt
        self._max_history = max_history
        # Outils (ToolRegistry duck-typé : `.specs()` + `.dispatch()`). Optionnel :
        # absent → comportement texte pur historique inchangé. Présent → boucle
        # function-calling activée (le LLM peut chercher sur le web, etc.).
        self._tools = tools
        self._tool_transport = tool_transport
        # Garde-fou anti-boucle : nb max d'allers-retours d'outils par énoncé.
        self._max_tool_hops = max_tool_hops
        # Historique par session : deque bornée à max_history tours (user+assistant).
        self._history: Dict[str, Deque[dict]] = {}
        # Contexte mémorisé long-terme injecté par MemoryStore à l'ouverture de session.
        self._memory_context: Dict[str, str] = {}
        # Contexte du PROJET actif (documents de l'utilisateur), injecté par ProjectStore.
        self._project_context: Dict[str, str] = {}
        self._skills_context: Dict[str, str] = {}
        self._client = None  # mémoïsé au 1er appel live

    async def reply(
        self,
        text: str,
        *,
        session_id: str,
        extra_tools: Optional[object] = None,
        system_override: Optional[str] = None,
        transports: Optional[tuple] = None,
    ) -> str:
        history = self._history.get(session_id, deque(maxlen=self._max_history * 2))
        messages: list[dict] = []
        # System = prompt de base + mémoire long-terme + projet actif (si présents).
        # `system_override` REMPLACE le prompt de base (ex. mode professeur d'anglais :
        # la règle « toujours en français » du prompt par défaut l'empêcherait de parler
        # anglais). La mémoire long-terme reste injectée : le tuteur sait à qui il parle.
        parts = [
            p
            for p in (
                system_override or self._system_prompt,
                self._memory_context.get(session_id),
                self._skills_context.get(session_id),
                self._project_context.get(session_id),
            )
            if p
        ]
        if parts:
            messages.append({"role": "system", "content": "\n\n".join(parts)})
        messages.extend(history)
        messages.append({"role": "user", "content": text})

        # Outils actifs pour CET énoncé : globaux (web) + éventuels outils de
        # session (projet de l'utilisateur), combinés sans muter le registre global.
        if extra_tools is not None and self._tools is not None:
            active_tools = self._tools.merged_with(extra_tools)
        else:
            active_tools = extra_tools if extra_tools is not None else self._tools

        # `transports` = (texte, outils) propres à CET appel : c'est ainsi qu'un
        # membre utilise SA clé et SON fournisseur, sans dupliquer l'objet LLM (la
        # mémoire, les projets et les compétences restent rangés par session).
        texte_tr, outils_tr = transports if transports else (None, None)
        if active_tools:
            response = await self._reply_with_tools(messages, active_tools, outils_tr)
        else:
            transport = texte_tr or self._transport or self._live_transport()
            response = await transport(messages)

        # Mise à jour de l'historique après réponse réussie. NB : seuls le tour
        # user et la réponse finale entrent dans l'historique long-terme — les
        # allers-retours d'outils restent internes à l'énoncé (pas de pollution).
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": response})
        self._history[session_id] = history
        return response

    async def _reply_with_tools(self, base: Sequence[dict], tools: object,
                                transport_override: Optional[object] = None) -> str:
        """Boucle function-calling : LLM ↔ outils jusqu'à une réponse en clair.

        `tools` = le registre actif pour cet énoncé (globaux + session). Contrat du
        `tool_transport` — `(messages, specs) -> dict` avec :
          - "content"    : texte de réponse (présent quand pas de tool_calls) ;
          - "tool_calls" : liste normalisée [{id, name, arguments}] à exécuter ;
          - "assistant"  : message assistant à réinjecter tel quel au tour suivant.
        """
        transport = transport_override or self._tool_transport or self._live_tool_transport()
        specs = tools.specs()
        work = list(base)
        for _ in range(self._max_tool_hops):
            out = await transport(work, specs)
            calls = out.get("tool_calls") or []
            if not calls:
                return out.get("content") or ""
            work.append(out["assistant"])  # assistant + ses tool_calls
            for call in calls:
                result = await tools.dispatch(call["name"], call.get("arguments"))
                work.append(
                    {
                        "role": "tool",
                        "name": call["name"],
                        "tool_call_id": call.get("id", ""),
                        "content": result,
                    }
                )
        # Hops épuisés : dernier appel SANS outils pour forcer une réponse parlée.
        final = await transport(work, [])
        return final.get("content") or "Désolée, je n'ai pas réussi à aboutir."

    def load_memory(self, session_id: str, context: str) -> None:
        """Injecte la mémoire long-terme d'un membre (appelé par le runtime à open())."""
        self._memory_context[session_id] = context

    def load_project(self, session_id: str, context: str) -> None:
        """Active un projet : injecte ses documents dans le contexte de la session.

        Canal distinct de la mémoire long-terme → activer/changer de projet ne
        touche pas aux souvenirs du membre. `context` vide désactive le projet.
        """
        if context:
            self._project_context[session_id] = context
        else:
            self._project_context.pop(session_id, None)

    def load_skills(self, session_id: str, context: str) -> None:
        """Injecte le SOMMAIRE des compétences (noms + descriptions), jamais leur contenu.

        Troisième canal, distinct de la mémoire et du projet : les compétences sont des
        méthodes, pas des souvenirs ni des données. Elles restent donc en place quand on
        change de projet.
        """
        if context:
            self._skills_context[session_id] = context
        else:
            self._skills_context.pop(session_id, None)

    def unload_memory(self, session_id: str) -> None:
        """Libère la mémoire, le projet actif et l'historique d'une session fermée."""
        self._memory_context.pop(session_id, None)
        self._project_context.pop(session_id, None)
        self._skills_context.pop(session_id, None)
        self._history.pop(session_id, None)

    def get_history(self, session_id: str) -> list:
        """Retourne l'historique de la session (pour extraction en fin de session)."""
        h = self._history.get(session_id)
        return list(h) if h else []

    def _live_transport(self) -> LlmTransport:
        async def _call(messages: Sequence[dict]) -> str:  # pragma: no cover - live
            client = self._lazy_client()
            resp = await client.chat.complete_async(
                model=self._model, messages=list(messages)
            )
            return resp.choices[0].message.content

        self._transport = _call  # n'enferme pas la lazy-init côté CI
        return _call

    def _live_tool_transport(self) -> "LlmToolTransport":  # pragma: no cover - live
        """Transport Mistral tool-aware : mappe l'API vers le contrat de la boucle."""

        async def _call(messages: Sequence[dict], specs: Sequence[dict]) -> dict:
            client = self._lazy_client()
            kwargs: dict = {"model": self._model, "messages": list(messages)}
            if specs:
                kwargs["tools"] = list(specs)
                kwargs["tool_choice"] = "auto"
            resp = await client.chat.complete_async(**kwargs)
            msg = resp.choices[0].message
            tool_calls = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,  # str JSON côté API
                }
                for tc in (getattr(msg, "tool_calls", None) or [])
            ]
            # Message assistant réinjectable tel quel au tour suivant (format API).
            assistant: dict = {"role": "assistant", "content": msg.content or ""}
            if tool_calls:
                assistant["tool_calls"] = [
                    {
                        "id": c["id"],
                        "type": "function",
                        "function": {"name": c["name"], "arguments": c["arguments"]},
                    }
                    for c in tool_calls
                ]
            return {"content": msg.content, "tool_calls": tool_calls, "assistant": assistant}

        self._tool_transport = _call
        return _call

    def _lazy_client(self):  # pragma: no cover - dépend de l'install live
        if self._client is None:
            try:
                from mistralai import Mistral
            except ImportError as exc:
                raise RuntimeError(
                    "mistralai non installé : `pip install mistralai` pour le live."
                ) from exc
            self._client = Mistral(api_key=_require_mistral_key())
        return self._client


class VoxtralSTT:
    """STT via Voxtral (Mistral audio, souveraineté UE). Implémente `STT`.

    Exemple (test) :  stt = VoxtralSTT(transport=fake_async_returning_text)
    """

    def __init__(
        self,
        transport: Optional[SttTransport] = None,
        *,
        model: str = DEFAULT_STT_MODEL,
    ) -> None:
        self._transport = transport
        self._model = model
        self._client = None

    async def transcribe(self, audio: object, locale: str) -> str:
        transport = self._transport or self._live_transport()
        return await transport(audio, locale)

    def _live_transport(self) -> SttTransport:
        async def _call(audio: object, locale: str) -> str:  # pragma: no cover - live
            client = self._lazy_client()
            # L'API attend un objet File {file_name, content}, pas des bytes bruts.
            resp = await client.audio.transcriptions.complete_async(
                model=self._model,
                file={"file_name": "utterance.wav", "content": bytes(audio)},
                language=locale.split("-")[0],
            )
            return resp.text

        self._transport = _call
        return _call

    def _lazy_client(self):  # pragma: no cover - dépend de l'install live
        if self._client is None:
            try:
                from mistralai import Mistral
            except ImportError as exc:
                raise RuntimeError(
                    "mistralai non installé : `pip install mistralai` pour le live."
                ) from exc
            self._client = Mistral(api_key=_require_mistral_key())
        return self._client


class CallableTTS:
    """TTS agnostique : délègue à un `transport` (texte, locale) -> bytes.

    Le fournisseur TTS souverain n'est pas encore tranché (décision Davy) :
    cet adaptateur EST le joint d'injection — on branchera le vrai backend
    (self-host Piper/Coqui, ou provider EU) derrière le même `transport`,
    sans toucher le runtime. Implémente `TTS`.
    """

    def __init__(self, transport: TtsTransport) -> None:
        self._transport = transport

    async def synthesize(self, text: str, locale: str) -> bytes:
        return await self._transport(text, locale)
