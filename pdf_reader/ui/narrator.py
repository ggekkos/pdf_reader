"""Reading aloud: generates the audio sentence by sentence and plays it in sequence.

The synthesizer runs on a separate thread, always a few sentences ahead of
what is playing, so the voice doesn't stop between sentences and the
interface doesn't freeze. On stop or a change of position, everything that
was queued is discarded (each reading "round" has a number, the ``generation``).
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QThread, QTimer, Signal, Slot
from PySide6.QtMultimedia import QAudio, QAudioFormat, QAudioSink, QMediaDevices

from pdf_reader.core.speech import Chunk, chunks_from, split_sentences
from pdf_reader.core.voices import Synthesizer, Voice, create_synthesizer, voice

_SENTENCES_AHEAD = 3
# "Buffer drained" (UnderrunError) is just the normal end of a sentence.
_SERIOUS_ERRORS = (QAudio.Error.OpenError, QAudio.Error.IOError, QAudio.Error.FatalError)


class _Worker(QObject):
    """Lives on the synthesis thread. Keeps the last loaded voice."""

    ready = Signal(int, int, object, int)  # generation, chunk id, pcm, rate
    failed = Signal(int, str)

    def __init__(self) -> None:
        super().__init__()
        self.current_generation = 0  # read from another thread: just an int, no lock
        self._key = ("", "")  # loaded (voice, folder)
        self._synthesizer: Synthesizer | None = None

    @Slot(int, int, str, str, str, float)
    def synthesize(self, generation: int, chunk_id: int, voice_id: str, folder: str, text: str,
                   speed: float) -> None:
        if generation != self.current_generation:
            return  # request from a reading that was already interrupted
        try:
            if (voice_id, folder) != self._key or self._synthesizer is None:
                self._synthesizer = create_synthesizer(voice(voice_id), Path(folder))
                self._key = (voice_id, folder)
            pcm = self._synthesizer.synthesize(text, speed)
            self.ready.emit(generation, chunk_id, pcm, self._synthesizer.rate)
        except Exception as error:  # corrupted model, missing engine...
            self._key, self._synthesizer = ("", ""), None
            self.failed.emit(generation, str(error) or type(error).__name__)


def _convert(pcm: bytes, rate: int, fmt: QAudioFormat) -> bytes:
    """Adapt the synthesizer's audio (16-bit, mono) to the sound card's format."""
    import numpy as np

    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
    if samples.size and fmt.sampleRate() != rate:
        n = max(round(samples.size * fmt.sampleRate() / rate), 1)
        samples = np.interp(np.linspace(0, samples.size - 1, n),
                            np.arange(samples.size), samples).astype(np.float32)
    channels = np.repeat(samples[:, None], max(fmt.channelCount(), 1), axis=1)
    kind = fmt.sampleFormat()
    if kind == QAudioFormat.SampleFormat.Float:
        return channels.astype(np.float32).tobytes()
    if kind == QAudioFormat.SampleFormat.Int32:
        return (channels * 2_147_483_647).astype(np.int32).tobytes()
    if kind == QAudioFormat.SampleFormat.UInt8:
        return (channels * 127 + 128).astype(np.uint8).tobytes()
    return (channels * 32_767).astype(np.int16).tobytes()


class Narrator(QObject):
    chunk_started = Signal(object)  # Chunk that started playing
    finished = Signal()  # reached the end of the document
    error = Signal(str)
    state_changed = Signal(bool)  # speaking or not

    _request = Signal(int, int, str, str, str, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._thread = QThread(self)
        self._worker = _Worker()
        self._worker.moveToThread(self._thread)
        self._request.connect(self._worker.synthesize)
        self._worker.ready.connect(self._ready)
        self._worker.failed.connect(self._failed)
        self._thread.start()

        self.speed = 1.0
        self._active = False
        self._generation = 0
        self._document = None
        self._voice = ""
        self._folder = ""
        self._planned: deque[Chunk] = deque()
        self._next_page = 0  # first page not yet split into sentences
        self._requested: dict[int, Chunk] = {}
        self._ready_chunks: dict[int, tuple[Chunk, bytes, int]] = {}
        self._next_request = 0
        self._next_to_play = 0
        self._playing = False
        self._words_generated = 0
        self._seconds_generated = 0.0

        self._sink: QAudioSink | None = None
        self._buffer: QBuffer | None = None
        self._stopping_audio = False  # the "stopped" that follows was requested by us

    # --- queries ---
    @property
    def active(self) -> bool:
        return self._active

    @property
    def words_per_minute(self) -> float:
        """The voice's actual pace so far (0 while there is no measurement)."""
        if self._seconds_generated < 5:
            return 0.0
        return 60 * self._words_generated / self._seconds_generated

    # --- control ---
    def speak(self, document, page: int, index: int, chosen: Voice, folder: Path) -> None:
        """Start (or restart) reading from word ``index`` of ``page``."""
        self._interrupt()
        self._document, self._voice, self._folder = document, chosen.id, str(folder)
        self._planned.extend(chunks_from(document.paragraphs(page), page, index))
        self._next_page = page + 1
        if not self._active:
            self._active = True
            self.state_changed.emit(True)
        self._queue_requests()

    def stop(self) -> None:
        self._interrupt()
        self._document = None
        if self._active:
            self._active = False
            self.state_changed.emit(False)

    def shutdown(self) -> None:
        """Stop everything and wait for the synthesis thread to finish (when closing the app)."""
        self.stop()
        self._thread.quit()
        self._thread.wait(5000)

    # --- internal: sentence queue ---
    def _interrupt(self) -> None:
        self._generation += 1
        self._worker.current_generation = self._generation
        self._planned.clear()
        self._requested.clear()
        self._ready_chunks.clear()
        self._next_request = self._next_to_play = 0
        self._playing = False
        self._stop_audio()

    def _next_chunk(self) -> Chunk | None:
        document = self._document
        while not self._planned:
            if document is None or self._next_page >= document.page_count:
                return None
            page = self._next_page
            self._next_page += 1
            self._planned.extend(split_sentences(document.paragraphs(page), page))
        return self._planned.popleft()

    def _queue_requests(self) -> None:
        while len(self._requested) + len(self._ready_chunks) < _SENTENCES_AHEAD:
            chunk = self._next_chunk()
            if chunk is None:
                break
            chunk_id = self._next_request
            self._next_request += 1
            self._requested[chunk_id] = chunk
            self._request.emit(self._generation, chunk_id, self._voice, self._folder, chunk.text,
                               self.speed)
        self._check_end()

    def _check_end(self) -> None:
        if self._active and not (self._playing or self._requested or self._ready_chunks
                                 or self._planned):
            if self._document is None or self._next_page >= self._document.page_count:
                self.stop()
                self.finished.emit()

    def _ready(self, generation: int, chunk_id: int, pcm: bytes, rate: int) -> None:
        if generation != self._generation or chunk_id not in self._requested:
            return
        chunk = self._requested.pop(chunk_id)
        pcm += bytes(2 * round(rate * chunk.pause_ms / 1000))  # silence after the sentence
        self._words_generated += chunk.end - chunk.start
        self._seconds_generated += len(pcm) / 2 / rate
        self._ready_chunks[chunk_id] = (chunk, pcm, rate)
        if not self._playing:
            self._play_next()

    def _failed(self, generation: int, message: str) -> None:
        if generation == self._generation:
            self.stop()
            self.error.emit(message)

    def _play_next(self) -> None:
        item = self._ready_chunks.pop(self._next_to_play, None)
        if item is None:  # the next sentence is still being generated
            self._playing = False
            self._check_end()
            return
        self._next_to_play += 1
        chunk, pcm, rate = item
        if not self._play(pcm, rate):
            return
        self._playing = True
        self.chunk_started.emit(chunk)
        self._queue_requests()

    # --- internal: audio ---
    def _play(self, pcm: bytes, rate: int) -> bool:
        device = QMediaDevices.defaultAudioOutput()
        if device.isNull():
            self.stop()
            self.error.emit("No audio output found.")
            return False
        fmt = QAudioFormat()
        fmt.setSampleRate(rate)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        if not device.isFormatSupported(fmt):
            fmt = device.preferredFormat()
            pcm = _convert(pcm, rate, fmt)

        if self._sink is None or self._sink.format() != fmt:
            if self._sink is not None:
                self._sink.stateChanged.disconnect(self._audio_state)
                self._sink.stop()
                self._sink.deleteLater()
            self._sink = QAudioSink(device, fmt, self)
            self._sink.stateChanged.connect(self._audio_state)

        previous = self._buffer
        self._buffer = QBuffer(self)
        self._buffer.setData(QByteArray(pcm))
        self._buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        # Restarting from the "idle" state doesn't report a state change, and
        # then the end of the sentence would go unnoticed: so stop first.
        self._stop_audio()
        self._sink.start(self._buffer)
        if previous is not None:
            previous.deleteLater()
        return True

    def _audio_state(self, state: QAudio.State) -> None:
        if not self._playing:
            return
        if state == QAudio.State.IdleState:  # the sentence just finished playing
            generation = self._generation  # if stopped before then, the notice is ignored
            QTimer.singleShot(0, lambda: generation == self._generation and self._play_next())
        elif state == QAudio.State.StoppedState and not self._stopping_audio:
            if self._sink.error() in _SERIOUS_ERRORS:
                self.stop()
                self.error.emit("Failed to play the audio.")

    def _stop_audio(self) -> None:
        if self._sink is None:
            return
        self._stopping_audio = True
        try:
            self._sink.stop()
        finally:
            self._stopping_audio = False
