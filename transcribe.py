"""Local, cancellable whisper.cpp transcription. No network calls at runtime."""
import os
from pathlib import Path
import subprocess
import tempfile
import time

BASE = Path(__file__).resolve().parent / '.local-whisper'


def paths():
    return BASE / 'whisper-cli', BASE / 'ggml-base.bin'


def available():
    binary, model = paths()
    return binary.is_file() and os.access(binary, os.X_OK) and model.is_file()


def transcribe(path, cancelled):
    binary, model = paths()
    if not available():
        raise RuntimeError('Whisper base не встановлено. Запустіть python3 setup_whisper.py у папці Meet Voice.')
    if cancelled.is_set():
        raise RuntimeError('Запит скасовано.')
    with tempfile.TemporaryDirectory(prefix='whisper-', dir=Path(path).parent) as directory:
        output = Path(directory) / 'transcript'
        # Output stays inside the private runtime directory and is deleted on exit.
        with (Path(directory) / 'error.log').open('wb') as log:
            proc = subprocess.Popen([str(binary), '-m', str(model), '-f', str(path),
                                     '-l', 'uk', '-t', '4', '-nt', '-np',
                                     '-otxt', '-of', str(output)],
                                    stdout=subprocess.DEVNULL, stderr=log)
            deadline = time.monotonic() + 240
            try:
                while proc.poll() is None:
                    if cancelled.wait(.1):
                        raise RuntimeError('Запит скасовано.')
                    if time.monotonic() > deadline:
                        raise RuntimeError('Whisper не завершив розпізнавання за 4 хвилини. Спробуйте коротший запис.')
                if cancelled.is_set():
                    raise RuntimeError('Запит скасовано.')
                if proc.returncode:
                    raise RuntimeError('Помилка локального Whisper. Перевірте модель або повторіть встановлення.')
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
        text = output.with_suffix('.txt').read_text().strip()
        if not text or text in {'[BLANK_AUDIO]', '(silence)', '[Silence]'}:
            raise RuntimeError('Whisper не розпізнав мовлення. Перевірте звук Meet і повторіть запис.')
        return text
