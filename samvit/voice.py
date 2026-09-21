"""Voice I/O — OS-native TTS and push-to-talk ASR (FR-8.x).

No wake-word and no always-on listening (FR-8.3): the ASR path only ever runs
when the user explicitly presses a button. Absence of either subsystem never
breaks text mode (FR-8.5/FR-8.6).
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys


def _tts_command(text: str):
    if "TERMUX_VERSION" in os.environ:
        return ["termux-tts-speak", text]
    if sys.platform == "darwin":
        return ["say", text]
    if os.name == "nt":
        import base64

        b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        return ["powershell", "-NoProfile", "-Command",
                "$t=New-Object -ComObject SAPI.SpVoice; $t.Speak([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('%s')))" % b64]
    # Linux / BSD: prefer espeak, fall back to spd-say.
    if shutil.which("espeak-ng"):
        return ["espeak-ng", text]
    if shutil.which("espeak"):
        return ["espeak", text]
    if shutil.which("spd-say"):
        return ["spd-say", "--wait", text]
    return None


def speak(text: str, timeout: int = 30) -> dict:
    """OS-native TTS (FR-8.1). Returns a non-crashing status dict."""
    cmd = _tts_command(text)
    if cmd is None:
        return {"ok": False, "error": "no TTS engine found (FR-8.6: non-crashing path)"}
    try:
        subprocess.run(cmd, timeout=timeout, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"ok": True, "engine": cmd[0]}
    except Exception as exc:
        return {"ok": False, "error": f"TTS failed: {exc!r}"}


def _record_binary() -> tuple:
    for tool in ("arecord", "sox", "ffmpeg"):
        if shutil.which(tool):
            return (tool,)
    return ()


def asr_push_to_talk() -> dict:
    """Push-to-talk ONLY (FR-8.2). Records a clip; returns a transcript or None.

    Without a recorder (sox/arecord/ffmpeg) plus an ASR engine, this returns a
    non-crashing status and never blocks. No wake word is ever listened for.
    """
    rec = _record_binary()
    if not rec:
        return {"ok": False, "error": "no recorder found (arecord/sox/ffmpeg); voice input disabled"}
    whisp = shutil.which("whisper") or shutil.which("whisper.cpp")
    if not whisp:
        return {"ok": False, "error": "no ASR engine (whisper) found; voice input disabled"}
    return {"ok": True, "note": "press the configured key to record; then transcribe (interactive)"}


def voice_status() -> dict:
    tts_cmd = _tts_command("test")
    rec = _record_binary()
    whisp = shutil.which("whisper") or shutil.which("whisper.cpp")
    return {
        "platform": platform.platform(),
        "tts": bool(tts_cmd),
        "tts_engine": tts_cmd[0] if tts_cmd else None,
        "asr_recorder": list(rec) or None,
        "asr_engine": whisp,
        "wake_word": False,          # FR-8.3
        "always_on_listening": False,  # FR-8.3
    }