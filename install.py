#!/usr/bin/python3
"""Register Firefox native host. Run without sudo from the permanent app folder."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
BASE=Path(__file__).resolve().parent

def main():
    if os.geteuid()==0:raise SystemExit('Запустіть без sudo.')
    missing=[name for name in ['parecord','pactl','grim','qs','firefox','ryoku','ryoku-hub','luac'] if not shutil.which(name)]
    if missing:raise SystemExit('Відсутні залежності: '+', '.join(missing))
    host=Path.home()/'.mozilla/native-messaging-hosts/ua.meet_voice.json'
    manifest={'name':'ua.meet_voice','description':'Meet Voice Gemini bridge','path':str(BASE/'meet_voice.py'),'type':'stdio','allowed_extensions':['meet-voice@local.invalid']}
    if host.exists() and json.loads(host.read_text()).get('path')!=manifest['path']:raise SystemExit('Інша копія Meet Voice вже зареєстрована: '+str(host))
    host.parent.mkdir(parents=True,exist_ok=True);host.write_text(json.dumps(manifest,indent=2)+'\n')
    (BASE/'meet_voice.py').chmod(0o755)
    subprocess.run(['/usr/bin/python3',str(BASE/'hotkeys.py'),'--install'],check=True)
    print('Native host:',host)
    print('Load Temporary Add-on:',BASE/'web/manifest.json')
    print('Спочатку виберіть чат Gemini. Super+Alt+V — увімкнути клавіші.')
if __name__=='__main__':main()
