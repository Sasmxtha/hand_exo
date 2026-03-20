"""
voice_control.py
Author: S. Sasmitha

Vosk offline speech recognition — low-latency voice commands.

Paper (Section III-A): Vosk 0.3.32 offline ASR processes commands
'open', 'close', 'stop' in a background thread.  A coordination
system gives priority to the last valid input between voice and
vision modules.
"""

import json
import queue
import threading
import time
from typing import Optional

try:
    import sounddevice as sd
    from vosk import Model, KaldiRecognizer
    _VOSK_OK = True
except ImportError:
    _VOSK_OK = False


class VoiceController:
    """
    Listens in a daemon thread, pushes recognised commands into a
    thread-safe queue.  Non-blocking: get_latest_command() returns
    the most recent command or None.
    """

    VALID = {"open", "close", "stop"}

    def __init__(self, model_path: str = "vosk-model-small-en-us-0.15",
                 sample_rate: int = 16_000):
        self._q:       queue.Queue = queue.Queue()
        self._running  = False
        self._thread:  Optional[threading.Thread] = None

        if not _VOSK_OK:
            return

        try:
            self._model = Model(model_path)
            self._rec   = KaldiRecognizer(self._model, sample_rate)
            self._sr    = sample_rate
            self._start()
        except Exception as e:
            print(f"[VoiceController] {e} — voice disabled")

    def _start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        def _cb(indata, frames, t, status):
            if self._rec.AcceptWaveform(bytes(indata)):
                text = json.loads(self._rec.Result()).get("text", "")
                for word in text.lower().split():
                    if word in self.VALID:
                        self._q.put(word)

        try:
            with sd.RawInputStream(samplerate=self._sr, blocksize=8000,
                                   dtype="int16", channels=1,
                                   callback=_cb):
                while self._running:
                    time.sleep(0.05)
        except Exception as e:
            print(f"[VoiceController] stream error: {e}")

    def get_latest_command(self) -> Optional[str]:
        """Non-blocking — returns most recent command or None."""
        cmd = None
        while not self._q.empty():
            try:
                cmd = self._q.get_nowait()
            except queue.Empty:
                break
        return cmd

    def stop(self):
        self._running = False
