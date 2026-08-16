"""Transports LLM multi-fournisseurs — chacun apporte sa clé.

La boucle d'outils de `MistralLLM` parle un seul dialecte interne, calqué sur celui
d'OpenAI : messages `{role, content}`, appels d'outils normalisés en
`{id, name, arguments}`. Plutôt que de dupliquer cette boucle par fournisseur, on
écrit ici des TRADUCTEURS : le transport reçoit l'historique au format interne, le
convertit vers le dialecte du fournisseur, puis reconvertit la réponse. Toute la
mécanique (mémoire, compétences, projets, isolation) reste donc inchangée.

Trois familles :
  - openai    : OpenAI, xAI (Grok), Mistral, DeepSeek, Groq — aucune conversion ;
  - anthropic : Claude — `system` sorti des messages, outils en `tool_use` /
    `tool_result` ;
  - google    : Gemini — rôles `user`/`model`, `functionCall` / `functionResponse`.

Les fonctions de conversion sont PURES et testées hors ligne ; seuls les appels
réseau (urllib, aucune dépendance tierce) échappent aux tests.
"""

from __future__ import annotations

import json
from typing import List, Optional, Sequence, Tuple

TIMEOUT = 120


# --------------------------------------------------------------------------- #
#  Famille OpenAI (dialecte natif de la boucle — conversion triviale)
# --------------------------------------------------------------------------- #

def openai_payload(messages: Sequence[dict], specs: Sequence[dict], model: str) -> dict:
    body: dict = {"model": model, "messages": list(messages)}
    if specs:
        body["tools"] = list(specs)
        body["tool_choice"] = "auto"
    return body


def openai_parse(data: dict) -> dict:
    msg = ((data.get("choices") or [{}])[0]).get("message") or {}
    calls = [
        {
            "id": tc.get("id", ""),
            "name": (tc.get("function") or {}).get("name", ""),
            "arguments": (tc.get("function") or {}).get("arguments", "{}"),
        }
        for tc in (msg.get("tool_calls") or [])
    ]
    return {"content": msg.get("content") or "", "tool_calls": calls, "assistant": msg}


# --------------------------------------------------------------------------- #
#  Famille Anthropic
# --------------------------------------------------------------------------- #

def anthropic_payload(messages: Sequence[dict], specs: Sequence[dict], model: str) -> dict:
    """Convertit l'historique interne vers le format Messages d'Anthropic.

    Différences traitées : le `system` est un paramètre à part (pas un message) ;
    un appel d'outil est un bloc `tool_use` dans le contenu de l'assistant ; un
    résultat d'outil est un bloc `tool_result` porté par un message `user`.
    """
    system_parts: List[str] = []
    out: List[dict] = []
    for m in messages:
        role = m.get("role")
        if role == "system":
            if m.get("content"):
                system_parts.append(str(m["content"]))
        elif role == "tool":
            bloc = {
                "type": "tool_result",
                "tool_use_id": m.get("tool_call_id") or "",
                "content": str(m.get("content") or ""),
            }
            # Anthropic accepte plusieurs résultats dans UN message user : on
            # regroupe les résultats consécutifs plutôt que d'en empiler autant
            # de messages (le modèle les relie ainsi au bon appel).
            if out and out[-1]["role"] == "user" and isinstance(out[-1].get("content"), list) \
                    and out[-1]["content"] and out[-1]["content"][0].get("type") == "tool_result":
                out[-1]["content"].append(bloc)
            else:
                out.append({"role": "user", "content": [bloc]})
        elif role == "assistant":
            blocs: List[dict] = []
            if m.get("content"):
                blocs.append({"type": "text", "text": str(m["content"])})
            for tc in (m.get("tool_calls") or []):
                fn = tc.get("function") or {}
                args = fn.get("arguments") or "{}"
                try:
                    args = json.loads(args) if isinstance(args, str) else args
                except json.JSONDecodeError:
                    args = {}
                blocs.append({"type": "tool_use", "id": tc.get("id", ""),
                              "name": fn.get("name", ""), "input": args})
            out.append({"role": "assistant", "content": blocs or [{"type": "text", "text": ""}]})
        else:
            out.append({"role": "user", "content": str(m.get("content") or "")})

    body: dict = {"model": model, "max_tokens": 4096, "messages": out}
    if system_parts:
        body["system"] = "\n\n".join(system_parts)
    if specs:
        body["tools"] = [
            {
                "name": (s.get("function") or {}).get("name", ""),
                "description": (s.get("function") or {}).get("description", ""),
                "input_schema": (s.get("function") or {}).get("parameters")
                                or {"type": "object", "properties": {}},
            }
            for s in specs
        ]
    return body


def anthropic_parse(data: dict) -> dict:
    texte, calls, blocs = [], [], data.get("content") or []
    for b in blocs:
        if b.get("type") == "text":
            texte.append(b.get("text") or "")
        elif b.get("type") == "tool_use":
            calls.append({
                "id": b.get("id", ""),
                "name": b.get("name", ""),
                "arguments": json.dumps(b.get("input") or {}, ensure_ascii=False),
            })
    # L'« assistant » est reinjecté tel quel au tour suivant : on le garde au format
    # interne pour que anthropic_payload sache le retraduire.
    assistant = {
        "role": "assistant",
        "content": "".join(texte),
        "tool_calls": [
            {"id": c["id"], "type": "function",
             "function": {"name": c["name"], "arguments": c["arguments"]}}
            for c in calls
        ],
    }
    return {"content": "".join(texte), "tool_calls": calls, "assistant": assistant}


# --------------------------------------------------------------------------- #
#  Famille Google (Gemini)
# --------------------------------------------------------------------------- #

def google_payload(messages: Sequence[dict], specs: Sequence[dict], model: str) -> dict:
    """Convertit vers le format generateContent (rôles user/model, functionCall)."""
    system_parts: List[str] = []
    contents: List[dict] = []
    for m in messages:
        role = m.get("role")
        if role == "system":
            if m.get("content"):
                system_parts.append(str(m["content"]))
        elif role == "tool":
            contents.append({"role": "user", "parts": [{"functionResponse": {
                "name": m.get("name") or "",
                "response": {"result": str(m.get("content") or "")},
            }}]})
        elif role == "assistant":
            parts: List[dict] = []
            if m.get("content"):
                parts.append({"text": str(m["content"])})
            for tc in (m.get("tool_calls") or []):
                fn = tc.get("function") or {}
                args = fn.get("arguments") or "{}"
                try:
                    args = json.loads(args) if isinstance(args, str) else args
                except json.JSONDecodeError:
                    args = {}
                parts.append({"functionCall": {"name": fn.get("name", ""), "args": args}})
            contents.append({"role": "model", "parts": parts or [{"text": ""}]})
        else:
            contents.append({"role": "user", "parts": [{"text": str(m.get("content") or "")}]})

    body: dict = {"contents": contents}
    if system_parts:
        body["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
    if specs:
        body["tools"] = [{"functionDeclarations": [
            {
                "name": (s.get("function") or {}).get("name", ""),
                "description": (s.get("function") or {}).get("description", ""),
                "parameters": (s.get("function") or {}).get("parameters")
                              or {"type": "object", "properties": {}},
            }
            for s in specs
        ]}]
    return body


def google_parse(data: dict) -> dict:
    cand = (data.get("candidates") or [{}])[0]
    parts = ((cand.get("content") or {}).get("parts")) or []
    texte, calls = [], []
    for i, p in enumerate(parts):
        if "text" in p:
            texte.append(p.get("text") or "")
        elif "functionCall" in p:
            fc = p["functionCall"]
            calls.append({
                # Gemini ne fournit pas d'identifiant d'appel : on en fabrique un
                # stable, la boucle en a besoin pour rattacher chaque résultat.
                "id": f"call_{i}",
                "name": fc.get("name", ""),
                "arguments": json.dumps(fc.get("args") or {}, ensure_ascii=False),
            })
    assistant = {
        "role": "assistant",
        "content": "".join(texte),
        "tool_calls": [
            {"id": c["id"], "type": "function",
             "function": {"name": c["name"], "arguments": c["arguments"]}}
            for c in calls
        ],
    }
    return {"content": "".join(texte), "tool_calls": calls, "assistant": assistant}


# --------------------------------------------------------------------------- #
#  Appel réseau (stdlib) et fabrique
# --------------------------------------------------------------------------- #

async def _post_json(url: str, headers: dict, body: dict) -> dict:  # pragma: no cover - réseau
    import asyncio
    import urllib.error
    import urllib.request

    def _call() -> dict:
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            raise RuntimeError(_message_clair(exc.code, detail)) from None

    return await asyncio.get_running_loop().run_in_executor(None, _call)


def _message_clair(code: int, detail: str) -> str:
    """Traduit l'échec du fournisseur en phrase actionnable pour l'utilisateur."""
    if code in (401, 403):
        return ("Ta clé API est refusée. Vérifie-la dans « Mon IA », ou "
                "régénère-la chez ton fournisseur.")
    if code == 429:
        return ("Ton fournisseur limite le rythme, ou ton crédit est épuisé. "
                "Réessaie dans un instant, ou vérifie ton solde chez lui.")
    if code == 402:
        return "Ton compte n'a plus de crédit chez ton fournisseur d'IA."
    if code == 404:
        return "Le modèle choisi n'existe pas chez ce fournisseur."
    return f"Ton fournisseur d'IA a répondu une erreur ({code}). {detail[:160]}"


def build_transports(famille: str, base_url: str, api_key: str, model: str) -> Tuple[object, object]:
    """(transport texte, transport outils) pour un fournisseur donné."""
    famille = (famille or "openai").lower()

    if famille == "anthropic":
        url = f"{base_url}/messages"
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        payload, parse = anthropic_payload, anthropic_parse
    elif famille == "google":
        url = f"{base_url}/models/{model}:generateContent?key={api_key}"
        headers = {}
        payload, parse = google_payload, google_parse
    else:
        url = f"{base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}
        payload, parse = openai_payload, openai_parse

    async def tool_transport(messages: Sequence[dict], specs: Sequence[dict]) -> dict:
        data = await _post_json(url, headers, payload(messages, specs, model))
        return parse(data)

    async def text_transport(messages: Sequence[dict]) -> str:
        out = await tool_transport(messages, [])
        return out.get("content") or ""

    return text_transport, tool_transport
