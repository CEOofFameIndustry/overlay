#!/usr/bin/python3
"""Register/toggle Meet Voice's own shortcuts through the Ryoku Hub writer."""
import fcntl
import json
from pathlib import Path
import shlex
import subprocess
import sys
import socket
import os

BASE=Path(__file__).resolve().parent
PREFIX='/usr/bin/python3 '+shlex.quote(str(BASE/'meet_voice.py'))
TOGGLE='/usr/bin/python3 '+shlex.quote(str(BASE/'hotkeys.py'))+' toggle'
CHORD='SUPER + ALT + V'
BINDINGS=[{'keys':'Right','action':'exec','value':PREFIX+' toggle','release':False},
          {'keys':'ALT + Right','action':'exec','value':PREFIX+' toggle-shot','release':False},
          {'keys':'MOD5 + Right','action':'exec','value':PREFIX+' toggle-shot','release':False},
          {'keys':'Left','action':'exec','value':PREFIX+' cancel','release':True}]

def run(args):return subprocess.run(args,check=True,capture_output=True,text=True,timeout=25).stdout

def cancel():
    path=Path(os.environ.get('XDG_RUNTIME_DIR',f'/tmp/gemini-dot-{os.getuid()}'))/'meet-voice/web.sock'
    if path.exists():
        try:
            with socket.socket(socket.AF_UNIX) as s:
                s.settimeout(3);s.connect(str(path));s.sendall(b'{"command":"cancel"}');s.recv(1024)
        except OSError:pass

def chord(value):return frozenset(value.upper().replace(' ','').split('+'))

def main():
    action=sys.argv[1] if len(sys.argv)>1 else 'toggle'
    if action not in ['toggle','enable','disable','status','--install','--remove']:raise RuntimeError('Unknown action')
    with (BASE/'.shortcuts.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        state=json.loads(run(['ryoku-hub','desktop','get']))
        binds=state['desktop'].get('keybinds',[])
        enabled=any(b.get('value')==PREFIX+' toggle' for b in binds)
        if action=='status':print('enabled' if enabled else 'disabled');return
        owned={PREFIX+' toggle',PREFIX+' toggle-shot',PREFIX+' cancel',TOGGLE}
        kept=[b for b in binds if b.get('value') not in owned]
        enable=not enabled if action=='toggle' else action=='enable'
        additions=[] if action=='--remove' else [{'keys':CHORD,'action':'exec','value':TOGGLE}]
        if enable:additions+=BINDINGS
        legend=json.loads(run(['ryoku-hub','keybinds']))
        for b in additions:
            if any(chord(v.get('keys',''))==chord(b['keys']) for v in kept):raise RuntimeError('Комбінація вже зайнята: '+b['keys'])
            if any(chord(v.get('chord',''))==chord(b['keys']) for c in legend.get('categories',[]) for v in c.get('binds',[]) if v.get('chord')) and not any(v.get('value') in owned and chord(v.get('keys',''))==chord(b['keys']) for v in binds):raise RuntimeError('Комбінація вже зайнята: '+b['keys'])
        state['desktop']['keybinds']=kept+additions
        run(['ryoku-hub','desktop','save',json.dumps(state)])
        run(['ryoku','wm','act','config.reload'])
        if not enable:cancel()
        from meet_voice import show
        show('Meet Voice увімкнено. → — запис / надіслати; правий Alt+→ — додати скриншот; ← — скасувати / прибрати вікно.' if enable else 'Meet Voice вимкнено. → працює звичайно. Super+Alt+V — увімкнути.',duration=5000)
        print('enabled' if enable else 'disabled')

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:
        print(str(e),file=sys.stderr);sys.exit(1)
