#!/usr/bin/python3
"""Create an unsigned Firefox package for Mozilla self-distribution signing."""
from pathlib import Path
import json
from zipfile import ZipFile, ZIP_DEFLATED
BASE=Path(__file__).resolve().parent
manifest=json.loads((BASE/'web/manifest.json').read_text())
output=BASE.parent/('voice-meet-'+manifest['version']+'-unsigned.zip')
with ZipFile(output,'w',ZIP_DEFLATED) as archive:
    for p in sorted((BASE/'web').iterdir()):
        if p.is_file() and p.suffix in {'.js','.json','.html'}:
            archive.write(p,p.name)
    archive.write(BASE/'PRIVACY.md','PRIVACY.md')
print(output)
