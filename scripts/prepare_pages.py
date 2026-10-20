#!/usr/bin/env python3
from pathlib import Path
import re, shutil
root=Path(__file__).resolve().parents[1]
settings=(root/'web/settings.js').read_text()
google="backend: 'google'" in settings or 'backend: "google"' in settings
ready=bool(re.search(r"https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec",settings)) if google else bool(re.search(r"apiBase:\s*['\"]https://[^'\"]+/api/['\"]",settings))
if not ready:raise SystemExit('Set the actual deployed HTTPS API address in web/settings.js before publishing Pages.')
shutil.copytree(root/'web',root/'docs',dirs_exist_ok=True)
(root/'docs/.nojekyll').touch()
print('GitHub Pages source prepared in docs/')
