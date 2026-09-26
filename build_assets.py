"""Publish PWA assets to Vercel's CDN; Flask serves the originals locally."""
from pathlib import Path
from shutil import copy2, copytree

root = Path(__file__).resolve().parent
public = root / 'public'
public.mkdir(exist_ok=True)
copytree(root / 'static', public / 'static', dirs_exist_ok=True)
copy2(root / 'static' / 'sw.js', public / 'sw.js')
