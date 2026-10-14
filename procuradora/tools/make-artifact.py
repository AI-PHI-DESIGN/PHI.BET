#!/usr/bin/env python3
"""Genera dist/artifact.html: el contenido de index.html sin el esqueleto <html>/<head>/<body>,
que es lo que exige la publicación como Artifact en claude.ai (allí el esqueleto lo pone la plataforma).
Se quitan además el manifest, los iconos y el service worker, que no aplican dentro del artefacto.
El lector de PDF (vendor/) se publica junto a la página como archivos aparte."""
import re, pathlib
src = pathlib.Path('index.html').read_text(encoding='utf-8')
head = re.search(r'<head>(.*?)</head>', src, re.S).group(1)
body = re.search(r'<body>(.*?)</body>', src, re.S).group(1)
head = re.sub(r'\s*<link rel="(manifest|icon|apple-touch-icon)"[^>]*>', '', head)
head = re.sub(r'\s*<meta charset="utf-8">|\s*<meta name="viewport"[^>]*>', '', head)
out = head.strip() + '\n' + body.strip() + '\n'
pathlib.Path('dist').mkdir(exist_ok=True)
pathlib.Path('dist/artifact.html').write_text(out, encoding='utf-8')
print('dist/artifact.html', len(out), 'bytes')
