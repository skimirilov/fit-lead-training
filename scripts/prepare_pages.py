#!/usr/bin/env python3
from pathlib import Path
import re, shutil
root=Path(__file__).resolve().parents[1]
settings=(root/'web/settings.js').read_text()
if not re.search(r"apiBase:\s*['\"]https://[^'\"]+/api/['\"]",settings):
 raise SystemExit('Set the actual HTTPS API address in web/settings.js before publishing Pages.')
shutil.copytree(root/'web',root/'docs',dirs_exist_ok=True)
(root/'docs/.nojekyll').touch()
print('GitHub Pages source prepared in docs/')
