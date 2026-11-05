import sys
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import transcribe

class Tests(unittest.TestCase):
    def executable(self, directory, code):
        p=Path(directory)/'whisper-cli'
        p.write_text('#!/usr/bin/python3\n'+code)
        p.chmod(0o755)
        model=Path(directory)/'model.bin';model.touch()
        clip=Path(directory)/'clip.wav';clip.touch()
        return p,model,clip

    def test_real_process_output_and_temp_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            binary,model,clip=self.executable(directory,"import sys\nfrom pathlib import Path\nPath(sys.argv[sys.argv.index('-of')+1]+'.txt').write_text('Два плюс два')\n")
            with patch.object(transcribe,'paths',return_value=(binary,model)):
                self.assertEqual(transcribe.transcribe(clip,threading.Event()),'Два плюс два')
            self.assertEqual(list(Path(directory).glob('whisper-*')), [binary])

    def test_cancel_stops_worker_and_cleans_transcript(self):
        with tempfile.TemporaryDirectory() as directory:
            binary,model,clip=self.executable(directory,'import time\ntime.sleep(30)\n')
            cancelled=threading.Event();timer=threading.Timer(.2,cancelled.set);timer.start()
            start=time.monotonic()
            with patch.object(transcribe,'paths',return_value=(binary,model)):
                with self.assertRaisesRegex(RuntimeError,'скасовано'):
                    transcribe.transcribe(clip,cancelled)
            timer.join();self.assertLess(time.monotonic()-start,3)
            self.assertEqual(list(Path(directory).glob('whisper-*')), [binary])

    def test_failed_worker_does_not_return_text(self):
        with tempfile.TemporaryDirectory() as directory:
            binary,model,clip=self.executable(directory,'raise SystemExit(2)\n')
            with patch.object(transcribe,'paths',return_value=(binary,model)):
                with self.assertRaisesRegex(RuntimeError,'Помилка'):
                    transcribe.transcribe(clip,threading.Event())

if __name__=='__main__':unittest.main()
