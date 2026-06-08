# Brief technique — câblage E/S audio LiveKit

> Contrats posés dans `shared/agent/audio/livekit_io.py` + `shared/agent/main.py`.
> Les parties réseau (SDK LiveKit) sont des squelettes TODO ; la logique pure est testée.

## Contrats

- **`LiveKitRoomOut.play(audio)`** — publie les frames audio TTS sur une piste de
  sortie de la room. Encadré par `HalfDuplexGate` (anti-larsen : capture suspendue
  pendant que l'agent parle).
- **`LiveKitAudioBridge`** — s'abonne aux pistes entrantes, alimente une VAD
  (`VoiceSegmenter`), émet les énoncés finalisés via `on_utterance(session_id, audio)`.
  Mapping room → session via `RoomSessionRegistry`.
- **`main.on_room_opened(...)`** — à l'ouverture d'une room : crée `SessionDescriptor`
  + `LiveKitRoomOut`, ouvre le runtime, branche `bridge.on_utterance = router.dispatch`.

## Contraintes (garde-fous)

- 1 personne = 1 device = 1 identité ; casques + half-duplex anti-larsen.
- `speaker_id` Voxtral = label de diarisation → résolu vers `member_id`
  (`RoomSessionRegistry.resolve_member`) ; jamais utilisé comme identité.
- Pas de traitement sans consentement (`SessionDescriptor.can_process`).

## Reste à câbler (TODO datés 2026-06-08)

- [ ] `LiveKitRoomOut.play` : création piste locale + capture_frame (livekit-rtc).
- [ ] `LiveKitAudioBridge.start` : abonnement `track_subscribed` + lecture frames → VAD.
- [ ] `Router.dispatch` : STT (Voxtral) → LLM (Mistral) → TTS → `RoomOut.play`.
- [ ] `main.run` : boucle de connexion LiveKit.
- [ ] Résolveur `speaker_id → member_id` adossé à la table `members` (post-validation DB).
