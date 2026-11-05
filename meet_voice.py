#!/usr/bin/python3
"""Push-to-record system audio -> selected Gemini Web chat -> protected overlay."""
import base64
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import uuid
import wave

import desktop_support as dot
import transport

BASE=Path(__file__).resolve().parent
MAX_SECONDS=180

def current_screen():
    state=transport.state()
    screen=state.get('focusedOutput')
    if not screen or screen not in {o['name'] for o in state.get('outputs',[])}:
        raise RuntimeError('Не вдалося визначити поточний монітор.')
    return screen

def show(text, screen=None, duration=90000):
    screen=screen or current_screen()
    text=str(text)[:12000]
    result=subprocess.run(['qs','ipc','-p',str(BASE/'overlay.qml'),'call','meetvoice','show',text,screen,str(duration)],capture_output=True,timeout=3)
    if result.returncode:
        env=os.environ.copy()
        env.update(MEET_VOICE_SCREEN=screen,MEET_VOICE_TEXT=text,MEET_VOICE_MS=str(duration))
        subprocess.Popen(['qs','-p',str(BASE/'overlay.qml')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)

def notify(text):
    print(str(text),file=sys.stderr,flush=True)
    try: show(text,duration=12000)
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError): pass

dot.notify=notify

class Host(transport.Host):
    def __init__(self):
        super().__init__()
        self.recording=None
        self.last_status='Виберіть чат Gemini у розширенні Meet Voice.'

    def command(self,command):
        if command=='status':
            result=super().command(command)
            with self.job_lock:
                result['recording']=self.recording is not None
                result['seconds']=round(time.monotonic()-self.recording['start'],1) if self.recording else 0
            return result
        if command in ('toggle','toggle-shot'):
            with self.job_lock:
                if not self.target.startswith('https://gemini.google.com/'):
                    return {'error':'Виберіть чат Gemini у розширенні Meet Voice.'}
                if self.job: return {'error':'Відповідь ще очікується. Спочатку скасуйте запит.'}
                if self.recording:
                    rec=self.recording;self.recording=None
                else:
                    self.start_recording(command=='toggle-shot')
                    return {'ok':True,'recording':True}
            self.submit_recording(rec,command=='toggle-shot')
            return {'ok':True,'recording':False}
        if command=='run':return {'error':'Використовуйте → для початку та завершення запису.'}
        return super().command(command)

    def start_recording(self,shot):
        dot.runtime()
        path=dot.RUNTIME/(str(uuid.uuid4())+'.wav')
        path.touch(mode=0o600)
        error_path=path.with_suffix('.log')
        with error_path.open('wb') as err:
            proc=subprocess.Popen(['parecord','--device=@DEFAULT_MONITOR@','--client-name=Meet Voice','--stream-name=Meet Voice recording','--rate=16000','--channels=1','--format=s16le','--latency-msec=50','--process-time-msec=20','--file-format=wav',str(path)],stdout=subprocess.DEVNULL,stderr=err)
        rec={'process':proc,'path':path,'start':time.monotonic(),'shot':shot,'errors':error_path}
        timer=threading.Timer(MAX_SECONDS,self.limit_recording,args=(rec,));timer.daemon=True
        rec['timer']=timer;self.recording=rec;timer.start()
        self.last_status='● Запис звуку. → — надіслати; правий Alt+→ — зі скриншотом.'
        show(self.last_status,duration=(MAX_SECONDS+5)*1000)

    def limit_recording(self,rec):
        with self.job_lock:
            if self.recording is not rec:return
            self.recording=None
        self.submit_recording(rec,False)

    def submit_recording(self,rec,shot):
        job={'id':str(uuid.uuid4()),'cancelled':threading.Event(),'reply_event':threading.Event(),'reply':None,'recording':rec,'shot':shot or rec['shot']}
        with self.job_lock:
            if self.job:
                self.stop_process(rec);self.cleanup(rec);return
            self.job=job
        self.last_status='Завершую запис…'
        threading.Thread(target=self.solve,args=(job,),daemon=True).start()

    @staticmethod
    def stop_process(rec):
        rec['timer'].cancel()
        proc=rec['process']
        if proc.poll() is None:
            proc.send_signal(signal.SIGINT)
            try:proc.wait(timeout=4)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=3)

    @staticmethod
    def cleanup(rec):
        rec['path'].unlink(missing_ok=True);rec['errors'].unlink(missing_ok=True)

    def cancel(self):
        with self.job_lock:
            rec=self.recording;self.recording=None
        if rec:self.stop_process(rec);self.cleanup(rec)
        super().cancel()
        self.last_status='Скасовано.'

    def solve(self,job):
        rec=job['recording']
        try:
            self.stop_process(rec)
            if job['cancelled'].is_set():return
            with wave.open(str(rec['path']),'rb') as audio:
                seconds=audio.getnframes()/audio.getframerate()
            if seconds<0.5:raise RuntimeError('Запис надто короткий. Натисніть →, дочекайтеся питання й натисніть → повторно.')
            files=[{'name':'MeetVoice-'+job['id']+'.wav','mime':'audio/wav','data':base64.b64encode(rec['path'].read_bytes()).decode()}]
            dot.hide()
            if job['shot']:
                png,_=dot.capture(current_screen())
                files.append({'name':'MeetVoice-'+job['id']+'.png','mime':'image/png','data':base64.b64encode(png).decode()})
            payload=base64.b64encode(json.dumps({'files':files},separators=(',',':')).encode()).decode()
            if len(payload)>28000000:raise RuntimeError('Запис завеликий. Зробіть коротший запис.')
            if job['cancelled'].is_set():return
            self.send({'type':'image-start','id':job['id'],'mime':'application/json'})
            for offset in range(0,len(payload),240000):
                if job['cancelled'].is_set():return
                self.send({'type':'image-chunk','id':job['id'],'data':payload[offset:offset+240000]})
            self.send({'type':'image-end','id':job['id']})
            self.last_status='Запис надіслано. Очікую Gemini…';show(self.last_status,duration=430000)
            deadline=time.monotonic()+420
            while not job['reply_event'].wait(.2):
                if job['cancelled'].is_set() or self.closed.is_set():return
                if time.monotonic()>deadline:
                    self.send({'type':'cancel','id':job['id']});raise RuntimeError('Gemini не відповів за 7 хвилин. Перевірте чат і ліміти.')
            if job['cancelled'].is_set():return
            reply=job['reply']
            if reply.get('type')=='error':raise RuntimeError(str(reply.get('message','Помилка розширення'))[:400])
            text=reply.get('text','')
            if not isinstance(text,str) or not text.strip():raise RuntimeError('Gemini повернув порожню відповідь.')
            self.last_status='Відповідь отримано.';show(text.strip())
        except (OSError,ValueError,RuntimeError,wave.Error,subprocess.SubprocessError) as err:
            if not job['cancelled'].is_set():self.notify(str(err))
        finally:
            self.cleanup(rec)
            with self.job_lock:
                if self.job is job:self.job=None

    def run(self):
        try:super().run()
        finally:
            rec=self.recording
            if rec:self.stop_process(rec);self.cleanup(rec)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1] in ['toggle','toggle-shot','status','cancel','diagnose']:
        sys.exit(transport.client(sys.argv[1]))
    Host().run()
