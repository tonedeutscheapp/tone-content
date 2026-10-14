#!/usr/bin/env python3
"""Build the TONE lexicon packs from open data (no AI).

Inputs (downloaded by the workflow into data/raw):
  dewiktionary.jsonl.gz  kaikki.org German-Wiktionary extract (CC BY-SA 4.0 / GFDL)
  de_50k.txt             FrequencyWords, OpenSubtitles 2018 (CC BY-SA 4.0)

Output (dist/):
  lexicon-<LEVEL>.json   lemma entries, one file per estimated CEFR band
  forms.json             inflected form -> lemma ids (lookup for the reader, typo help)
  lexicon-stats.json     counts used by validate_packs.py and the manifest

Entry keys (short on purpose; the app maps them):
  id lemma, l lemma, p pos, g gender (m/f/n), a article, pl plural, gs genitive sg,
  vf verb forms [3sg present, Präteritum, Partizip II], aux haben/sein, ipa, hy hyphenation,
  tr / en translations, de German definitions (B2+ monolingual), ex examples, r frequency rank, lv band
"""
import gzip, json, re, sys, collections, os

RAW = sys.argv[1] if len(sys.argv) > 1 else 'data/raw'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'dist'
os.makedirs(OUT, exist_ok=True)

POS = {'noun': 'n', 'verb': 'v', 'adj': 'adj', 'adv': 'adv', 'prep': 'prep', 'conj': 'conj',
       'pron': 'pron', 'det': 'det', 'article': 'det', 'num': 'num', 'intj': 'intj',
       'particle': 'part', 'phrase': 'phr', 'proverb': 'phr', 'abbrev': 'abbr', 'postp': 'prep'}
# CEFR bands estimated from lemma frequency rank. This is an estimate, not an official list;
# hand-built units (tone-app/content/units) always override it.
BANDS = [(800, 'A1'), (1800, 'A2'), (3500, 'B1'), (7000, 'B2'), (14000, 'C1')]
WORD_RE = re.compile(r"^[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß' .-]{0,40}$")
ART_RE = re.compile(r'^(der|die|das|des|dem|den)\s+')
REF_RE = re.compile(r'\[\d+[a-z]?\]\s*')


def band(rank):
    if rank is None:
        return 'C2'
    for lim, b in BANDS:
        if rank <= lim:
            return b
    return 'C2'


def clean(s):
    return REF_RE.sub('', s or '').strip()


def freq_counts(path):
    c = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            parts = line.split()
            if len(parts) == 2 and parts[1].isdigit():
                c[parts[0]] = int(parts[1])
    return c


def has(tags, *want):
    return all(w in tags for w in want)


def main():
    freq = freq_counts(os.path.join(RAW, 'de_50k.txt'))
    entries = collections.OrderedDict()   # (lemma, pos) -> entry
    form_map = collections.defaultdict(set)
    lines = bad = 0
    with gzip.open(os.path.join(RAW, 'dewiktionary.jsonl.gz'), 'rt', encoding='utf-8') as f:
        for line in f:
            lines += 1
            try:
                d = json.loads(line)
            except ValueError:
                bad += 1
                continue
            if d.get('lang_code') != 'de':
                continue
            w = d.get('word', '').strip()
            p = POS.get(d.get('pos', ''))
            if not p or not WORD_RE.match(w):
                continue
            senses = d.get('senses') or []
            # skip pure inflected-form pages ("Häuser" -> form of "Haus"); they feed forms.json
            if senses and all(s.get('form_of') for s in senses):
                for s in senses:
                    for fo in s.get('form_of', []):
                        if fo.get('word'):
                            form_map[w].add((fo['word'], p))
                continue
            key = (w, p)
            e = entries.get(key)
            if e is None:
                e = {'l': w, 'p': p}
                entries[key] = e
            tags = set(d.get('tags') or [])
            for g, code in (('masculine', 'm'), ('feminine', 'f'), ('neuter', 'n')):
                if g in tags and p == 'n':
                    e.setdefault('g', code)
            for s in d.get('sounds') or []:
                if s.get('ipa') and 'ipa' not in e:
                    e['ipa'] = s['ipa']
            for h in d.get('hyphenations') or []:
                if h.get('parts') and 'hy' not in e:
                    e['hy'] = '·'.join(h['parts'])
            de_gl, ex = e.setdefault('de', []), e.setdefault('ex', [])
            for s in senses:
                for g in s.get('glosses') or []:
                    g = clean(g)
                    if g and len(de_gl) < 4 and g not in de_gl:
                        de_gl.append(g[:220])
                for x in s.get('examples') or []:
                    t = clean(x.get('text'))
                    if t and 12 <= len(t) <= 160 and len(ex) < 3 and '[' not in t:
                        ex.append(t)
            tr, en = e.setdefault('tr', []), e.setdefault('en', [])
            for t in d.get('translations') or []:
                word = (t.get('word') or '').strip()
                if not word or len(word) > 60:
                    continue
                lc = t.get('lang_code')
                if lc == 'tr' and word not in tr and len(tr) < 6:
                    tr.append(word)
                elif lc == 'en' and word not in en and len(en) < 6:
                    en.append(word)
            vf = e.get('vf') or ['', '', '']
            for fo in d.get('forms') or []:
                form = (fo.get('form') or '').strip()
                ft = set(fo.get('tags') or [])
                if not form or form == '—' or len(form) > 50:
                    continue
                if fo.get('article') and p == 'n' and 'a' not in e and has(ft, 'nominative', 'singular'):
                    e['a'] = fo['article']
                if p == 'n':
                    bare = ART_RE.sub('', form)
                    if has(ft, 'nominative', 'plural') and 'pl' not in e:
                        e['pl'] = bare
                    if has(ft, 'genitive', 'singular') and 'gs' not in e:
                        e['gs'] = bare
                if p == 'v':
                    if has(ft, 'present', 'third-person', 'singular') and not vf[0]:
                        vf[0] = form
                    elif has(ft, 'past', 'first-person', 'singular') and 'subjunctive-ii' not in ft and not vf[1]:
                        vf[1] = form
                    elif has(ft, 'participle', 'past') and not vf[2]:
                        vf[2] = form
                    if 'auxiliary' in ft and form in ('haben', 'sein') and 'aux' not in e:
                        e['aux'] = form
                for piece in form.split():
                    if piece != w and WORD_RE.match(piece) and piece not in ('der', 'die', 'das', 'des', 'dem', 'den', 'ich', 'du', 'er', 'sie', 'es', 'wir', 'ihr', 'hat', 'ist', 'hast', 'bist', 'habe', 'bin', 'sind', 'seid', 'habt', 'haben', 'sein', 'hätte', 'wäre', 'würde', 'werden', 'wurde', 'worden', 'man'):
                        form_map[piece].add((w, p))
            if p == 'v' and any(vf):
                e['vf'] = vf
            if p == 'n' and 'a' not in e and e.get('g'):
                e['a'] = {'m': 'der', 'f': 'die', 'n': 'das'}[e['g']]

    # lemma frequency = own count + counts of its inflected forms
    lemma_freq = collections.Counter()
    for (w, p) in entries:
        lemma_freq[(w, p)] += freq.get(w, 0) + freq.get(w.lower(), 0)
    for form, owners in form_map.items():
        n = freq.get(form, 0) + (freq.get(form.lower(), 0) if form.lower() != form else 0)
        if not n:
            continue
        own = [o for o in owners if o in entries]
        for o in own:
            lemma_freq[o] += n // len(own)

    kept = []
    for key, e in entries.items():
        for k in ('tr', 'en', 'de', 'ex'):
            if not e.get(k):
                e.pop(k, None)
        if not (e.get('tr') or e.get('en') or e.get('de')):
            continue
        kept.append((key, e))
    ranked = sorted((k for k, _ in kept if lemma_freq[k] > 0), key=lambda k: -lemma_freq[k])
    rank = {k: i + 1 for i, k in enumerate(ranked)}
    ids, by_band = {}, collections.defaultdict(list)
    used = set()
    for key, e in kept:
        base = re.sub(r'[^a-z0-9äöüß]+', '-', e['l'].lower()).strip('-') or 'x'
        i = f"{base}.{e['p']}"
        while i in used:
            i += '2'
        used.add(i)
        ids[key] = i
        e = {'id': i, **e}
        r = rank.get(key)
        if r:
            e['r'] = r
        e['lv'] = band(r)
        by_band[e['lv']].append(e)
    for b, lst in by_band.items():
        lst.sort(key=lambda e: e.get('r', 10**9))
        with open(os.path.join(OUT, f'lexicon-{b}.json'), 'w', encoding='utf-8') as f:
            json.dump({'band': b, 'entries': lst}, f, ensure_ascii=False, separators=(',', ':'))
    forms_out = {}
    for form, owners in form_map.items():
        own = sorted({ids[o] for o in owners if o in ids})
        if own:
            forms_out[form] = own
    with open(os.path.join(OUT, 'forms.json'), 'w', encoding='utf-8') as f:
        json.dump(forms_out, f, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    # lemma -> id map for the sentence builder
    lm = {}
    for (w, p), i in ids.items():
        lm.setdefault(w, i)
        lm.setdefault(w.lower(), i)
    for form, own in forms_out.items():
        lm.setdefault(form, own[0])
        lm.setdefault(form.lower(), own[0])
    with open(os.path.join(OUT, '_formindex.json'), 'w', encoding='utf-8') as f:
        json.dump({'lemma': lm, 'rank': {i: rank.get(k) for k, i in ids.items() if rank.get(k)}}, f, ensure_ascii=False)
    stats = {'lines': lines, 'bad_lines': bad, 'lemmas': len(ids), 'forms': len(forms_out),
             'with_tr': sum(1 for _, e in kept if e.get('tr')), 'with_en': sum(1 for _, e in kept if e.get('en')),
             'bands': {b: len(v) for b, v in sorted(by_band.items())}}
    with open(os.path.join(OUT, 'lexicon-stats.json'), 'w') as f:
        json.dump(stats, f, indent=1)
    print(json.dumps(stats))


if __name__ == '__main__':
    main()
