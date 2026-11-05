import base64
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import wave
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import meet_voice as app

class Tests(unittest.TestCase):
    def test_current_output_not_fixed_workspace_one(self):
        with patch.object(app.transport,'state',return_value={'focusedOutput':'HDMI-A-1','outputs':[{'name':'HDMI-A-1'}]}):
            self.assertEqual(app.current_screen(),'HDMI-A-1')

    def test_second_right_stops_and_submits(self):
        host=app.Host();host.target='https://gemini.google.com/app/test'
        rec={'shot':False};host.recording=rec
        with patch.object(host,'submit_recording') as submit:
            self.assertTrue(host.command('toggle')['ok']);submit.assert_called_once_with(rec,False)
        self.assertIsNone(host.recording)

    def test_alt_right_adds_screenshot(self):
        host=app.Host();host.target='https://gemini.google.com/app/test';rec={'shot':False};host.recording=rec
        with patch.object(host,'submit_recording') as submit:
            host.command('toggle-shot');submit.assert_called_once_with(rec,True)

    def test_cannot_record_before_selecting_chat(self):
        with patch.object(app.subprocess,'Popen') as popen:
            self.assertIn('error',app.Host().command('toggle'));popen.assert_not_called()

    def make_recording(self,directory):
        path=Path(directory)/'clip.wav'
        with wave.open(str(path),'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(b'\0\0'*16000)
        error=Path(directory)/'clip.log';error.touch()
        return {'path':path,'errors':error,'shot':False}

    def roundtrip(self,shot=False,cancelled=False):
        with tempfile.TemporaryDirectory() as directory:
            host=app.Host();rec=self.make_recording(directory)
            job={'id':'test','recording':rec,'shot':shot,'cancelled':threading.Event(),'reply_event':threading.Event(),'reply':None}
            if cancelled:job['cancelled'].set()
            host.job=job;sent=[];parts=[]
            def send(msg):
                sent.append(msg['type'])
                if msg['type']=='image-chunk':parts.append(msg['data'])
                if msg['type']=='image-end':
                    job['reply']={'type':'answer','text':'Чотири.'};job['reply_event'].set()
            with patch.object(host,'stop_process'),patch.object(host,'send',side_effect=send),patch.object(app.dot,'hide'),patch.object(app.dot,'capture',return_value=(b'png',None)) as capture,patch.object(app,'show') as show,patch.object(app,'current_screen',return_value='HDMI-A-1'):
                host.solve(job)
                if not cancelled:show.assert_called_with('Чотири.')
                self.assertEqual(capture.call_count,1 if shot and not cancelled else 0)
            self.assertIsNone(host.job)
            self.assertFalse(rec['path'].exists())
            return json.loads(base64.b64decode(''.join(parts))) if parts else None

    def test_audio_only_roundtrip(self):
        bundle=self.roundtrip()
        self.assertEqual([f['mime'] for f in bundle['files']],['audio/wav'])
        self.assertTrue(base64.b64decode(bundle['files'][0]['data']).startswith(b'RIFF'))

    def test_audio_and_screenshot_roundtrip(self):
        self.assertEqual([f['mime'] for f in self.roundtrip(True)['files']],['audio/wav','image/png'])

    def test_cancel_does_not_send_audio(self):self.assertIsNone(self.roundtrip(cancelled=True))

if __name__=='__main__':unittest.main()
