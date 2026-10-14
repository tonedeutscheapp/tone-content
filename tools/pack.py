#!/usr/bin/env python3
"""Validate the built packs, gzip them and write manifest.json.

The app reads manifest.json first, compares each file's sha256 with its cache and downloads only
changed packs (delta updates per pack). gzip is used because Android (dart:io) and browsers
(DecompressionStream) decode it natively.
Usage: pack.py dist out [--min-lemmas N] [--min-sentences N]
"""
import gzip, hashlib, json, os, sys, datetime

src, out = sys.argv[1], sys.argv[2]
args = sys.argv[3:]
def opt(name, d):
    return int(args[args.index(name) + 1]) if name in args else d
MIN_LEMMAS, MIN_SENT = opt('--min-lemmas', 1000), opt('--min-sentences', 1000)
os.makedirs(out, exist_ok=True)
errors = []

LEX_KEYS = {'id', 'l', 'p', 'g', 'a', 'pl', 'gs', 'vf', 'aux', 'ipa', 'hy', 'tr', 'en', 'de', 'ex', 'r', 'lv'}
ids = set()
lemmas = 0
for fn in sorted(os.listdir(src)):
    if fn.startswith('lexicon-') and fn != 'lexicon-stats.json':
        d = json.load(open(os.path.join(src, fn), encoding='utf-8'))
        for e in d['entries']:
            lemmas += 1
            if set(e) - LEX_KEYS:
                errors.append(f'{fn}: unknown keys {set(e) - LEX_KEYS} in {e.get("id")}')
            if e['id'] in ids:
                errors.append(f'{fn}: duplicate id {e["id"]}')
            ids.add(e['id'])
            if not (e.get('tr') or e.get('en') or e.get('de')):
                errors.append(f'{fn}: {e["id"]} has no meaning')
            if e['lv'] != d['band']:
                errors.append(f'{fn}: {e["id"]} band mismatch')
sents = 0
for fn in sorted(os.listdir(src)):
    if fn.startswith('sentences-') and fn != 'sentences-stats.json':
        d = json.load(open(os.path.join(src, fn), encoding='utf-8'))
        for s in d['sentences']:
            sents += 1
            if not s.get('de') or not (s.get('tr') or s.get('en')):
                errors.append(f'{fn}: sentence {s.get("i")} incomplete')
            for w in s.get('w', []):
                if w not in ids:
                    errors.append(f'{fn}: sentence {s["i"]} -> unknown lemma {w}')
                    break
forms = json.load(open(os.path.join(src, 'forms.json'), encoding='utf-8'))
for f, own in forms.items():
    for o in own:
        if o not in ids:
            errors.append(f'forms.json: {f} -> unknown {o}')
if lemmas < MIN_LEMMAS:
    errors.append(f'only {lemmas} lemmas (< {MIN_LEMMAS})')
if sents < MIN_SENT:
    errors.append(f'only {sents} sentences (< {MIN_SENT})')
if errors:
    print('\n'.join(errors[:50]))
    print(f'{len(errors)} errors')
    sys.exit(1)

files = []
for fn in sorted(os.listdir(src)):
    if not fn.endswith('.json') or fn.startswith('_') or fn.endswith('-stats.json'):
        continue
    raw = open(os.path.join(src, fn), 'rb').read()
    gz = gzip.compress(raw, 9, mtime=0)
    open(os.path.join(out, fn + '.gz'), 'wb').write(gz)
    kind = fn.split('-')[0].split('.')[0]
    band = fn[:-5].split('-')[1] if fn.count('-') == 1 and kind in ('lexicon', 'sentences') else None
    files.append({'name': fn + '.gz', 'kind': kind, 'band': band, 'bytes': len(gz), 'raw_bytes': len(raw),
                  'sha256': hashlib.sha256(gz).hexdigest()})
stats = {}
for s in ('lexicon-stats.json', 'sentences-stats.json'):
    p = os.path.join(src, s)
    if os.path.exists(p):
        stats[s.split('-')[0]] = json.load(open(p))
manifest = {
    'schema': 1,
    'version': datetime.datetime.now(datetime.timezone.utc).strftime('%Y.%m.%d.%H%M'),
    'files': files,
    'stats': stats,
    'licenses': {
        'lexicon': 'Wiktionary (de.wiktionary.org) via kaikki.org/wiktextract, CC BY-SA 4.0 / GFDL',
        'frequency': 'FrequencyWords by Hermit Dave (OpenSubtitles 2018), CC BY-SA 4.0',
        'sentences': 'Tatoeba (tatoeba.org), CC BY 2.0 FR; sentence ids link to their authors',
    },
}
json.dump(manifest, open(os.path.join(out, 'manifest.json'), 'w'), indent=1)
print(f'ok: {lemmas} lemmas, {len(forms)} forms, {sents} sentences, {len(files)} packs, '
      f'{sum(f["bytes"] for f in files) / 1e6:.1f} MB gz')
