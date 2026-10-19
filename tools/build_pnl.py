# Build the GitHub Pages (home-screen app) version from the artifact source.
import sys, re, pathlib
src = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
out = pathlib.Path(sys.argv[2])
src = src.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', '')
assert 'waitForClaude(2000)' in src
src = src.replace('waitForClaude(2000)', 'waitForClaude(0)')  # no Claude runtime here: use iPhone storage immediately
i = src.index('<div class="wrap">')
head, body = src[:i], src[i:]
head = re.sub(r'<title>.*?</title>\n', '', head)
skel = '''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title>収支ノート</title>
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="収支ノート">
<meta name="theme-color" content="#EDF0F3" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0D141C" media="(prefers-color-scheme: dark)">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icon2-180.png">
<link rel="icon" href="icon2-192.png">
'''
tail = '\n' + pathlib.Path(__file__).with_name('pnl_import_snippet.html').read_text(encoding='utf-8') + '''
<script>if ('serviceWorker' in navigator) { window.addEventListener('load', function () { navigator.serviceWorker.register('sw.js').catch(function () {}); }); }</script>
</body>
</html>
'''
out.write_text(skel + head + '</head>\n<body>\n' + body + tail, encoding='utf-8')
print('ok', out, len(skel + head + body + tail))
