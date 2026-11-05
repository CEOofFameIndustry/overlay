#!/usr/bin/python3
"""Install multilingual base and a pinned whisper.cpp locally, without sudo."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parent / '.local-whisper'
COMMIT = 'b1535f5fb163f4443804888f7be980621226cb15'
MODEL_SHA1 = '465707469ff3a37a2b9b8d8f89f2f99de7299dac'


def run(*args):
    subprocess.run(list(args), check=True)


def main():
    for command in ('git', 'cmake', 'c++'):
        if not shutil.which(command):
            raise SystemExit('Відсутня залежність: ' + command)
    ROOT.mkdir(exist_ok=True)
    source = ROOT / 'source'
    binary = ROOT / 'whisper-cli'
    if not binary.is_file():
        if not source.exists():
            run('git', 'init', str(source))
            run('git', '-C', str(source), 'remote', 'add', 'origin', 'https://github.com/ggml-org/whisper.cpp.git')
        run('git', '-C', str(source), 'fetch', '--depth', '1', 'origin', COMMIT)
        run('git', '-C', str(source), 'checkout', '--detach', COMMIT)
        run('cmake', '-S', str(source), '-B', str(source / 'build'),
            '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_SHARED_LIBS=OFF', '-DGGML_CCACHE=OFF',
            '-DWHISPER_BUILD_TESTS=OFF', '-DWHISPER_BUILD_SERVER=OFF',
            '-DGGML_CUDA=OFF', '-DGGML_VULKAN=OFF')
        run('cmake', '--build', str(source / 'build'), '--target', 'whisper-cli', '-j', '4')
        shutil.copy2(source / 'build/bin/whisper-cli', binary)
        shutil.copy2(source / 'LICENSE', ROOT / 'LICENSE-whisper.cpp')
    model = ROOT / 'ggml-base.bin'
    if not model.is_file() or hashlib.sha1(model.read_bytes()).hexdigest() != MODEL_SHA1:
        part = model.with_suffix('.part')
        print('Завантаження багатомовної Whisper base (~142 МіБ)…', flush=True)
        with urllib.request.urlopen('https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin', timeout=60) as response, part.open('wb') as out:
            shutil.copyfileobj(response, out)
        if hashlib.sha1(part.read_bytes()).hexdigest() != MODEL_SHA1:
            part.unlink(missing_ok=True)
            raise SystemExit('Контрольна сума моделі не збігається.')
        part.replace(model)
    print('Whisper base встановлено. Модель: ' + str(model))


if __name__ == '__main__':
    main()
