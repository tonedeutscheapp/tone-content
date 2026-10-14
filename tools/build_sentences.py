#!/usr/bin/env python3
"""Build the TONE sentence bank from Tatoeba (CC BY 2.0 FR; each sentence keeps its Tatoeba id
so attribution links back to https://tatoeba.org/sentences/show/<id>).

Inputs (data/raw): deu_sentences.tsv, tur_sentences.tsv, eng_sentences.tsv,
                   deu-tur_links.tsv, deu-eng_links.tsv   (id<TAB>lang<TAB>text / id<TAB>id)
                   dist/_formindex.json from build_lexicon.py
Output (dist/):    sentences-<LEVEL>.json  {i, de, tr[], en[], w[lemma ids], lv}
                   word-sentences.json     lemma id -> up to 12 sentence ids (easiest first)
"""
import json, os, re, sys, collections

RAW = sys.argv[1] if len(sys.argv) > 1 else 'data/raw'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'dist'
TOK = re.compile(r"[A-Za-zÄÖÜäöüß]+(?:-[A-Za-zÄÖÜäöüß]+)*")
BANDS = [(800, 'A1'), (1800, 'A2'), (3500, 'B1'), (7000, 'B2'), (14000, 'C1')]


def band(r):
    for lim, b in BANDS:
        if r <= lim:
            return b
    return 'C2'


def read_sent(name):
    out = {}
    p = os.path.join(RAW, name)
    with open(p, encoding='utf-8') as f:
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 3:
                out[parts[0]] = parts[2].strip()
    return out


def read_links(name, src):
    m = collections.defaultdict(list)
    with open(os.path.join(RAW, name), encoding='utf-8') as f:
        for line in f:
            a, _, b = line.strip().partition('\t')
            if a in src:
                m[a].append(b)
            elif b in src:
                m[b].append(a)
    return m


def main():
    idx = json.load(open(os.path.join(OUT, '_formindex.json'), encoding='utf-8'))
    lemma, rank = idx['lemma'], idx['rank']
    de = read_sent('deu_sentences.tsv')
    tr, en = read_sent('tur_sentences.tsv'), read_sent('eng_sentences.tsv')
    ltr, len_ = read_links('deu-tur_links.tsv', de), read_links('deu-eng_links.tsv', de)
    by_band = collections.defaultdict(list)
    word_sent = collections.defaultdict(list)
    seen_text = set()
    for sid, text in de.items():
        t_tr = [tr[x] for x in ltr.get(sid, []) if x in tr][:3]
        t_en = [en[x] for x in len_.get(sid, []) if x in en][:3]
        if not (t_tr or t_en):
            continue
        if not (3 <= len(text) <= 220) or text in seen_text:
            continue
        seen_text.add(text)
        toks = TOK.findall(text)
        if not toks or len(toks) > 30:
            continue
        ws, ranks, unknown = [], [], 0
        for i, tk in enumerate(toks):
            lid = lemma.get(tk) or (lemma.get(tk.lower()) if i == 0 or tk.lower() == tk else None) or lemma.get(tk.lower())
            if lid:
                if lid not in ws:
                    ws.append(lid)
                ranks.append(rank.get(lid, 20000))
            elif i > 0 and tk[0].isupper():
                continue          # unknown capitalised word inside a sentence: most likely a name
            else:
                unknown += 1
                ranks.append(20000)
        if not ranks:
            continue
        ranks.sort()
        # difficulty = rank of the 2nd hardest word (one rare name or word does not make a sentence C2),
        # plus length: long sentences move up one band.
        hard = ranks[-2] if len(ranks) >= 2 else ranks[-1]
        lv = band(hard)
        if len(toks) > 14 and lv in ('A1', 'A2', 'B1'):
            lv = {'A1': 'A2', 'A2': 'B1', 'B1': 'B2'}[lv]
        e = {'i': int(sid), 'de': text, 'lv': lv, 'w': ws}
        if t_tr:
            e['tr'] = t_tr
        if t_en:
            e['en'] = t_en
        by_band[lv].append(e)
        score = hard * 100 + len(toks)
        for lid in ws:
            word_sent[lid].append((score, int(sid)))
    for b, lst in by_band.items():
        lst.sort(key=lambda e: e['i'])
        with open(os.path.join(OUT, f'sentences-{b}.json'), 'w', encoding='utf-8') as f:
            json.dump({'band': b, 'source': 'tatoeba', 'sentences': lst}, f, ensure_ascii=False, separators=(',', ':'))
    ws_out = {k: [s for _, s in sorted(v)[:12]] for k, v in word_sent.items()}
    with open(os.path.join(OUT, 'word-sentences.json'), 'w', encoding='utf-8') as f:
        json.dump(ws_out, f, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    stats = {'sentences': sum(len(v) for v in by_band.values()),
             'with_tr': sum(1 for v in by_band.values() for e in v if 'tr' in e),
             'bands': {b: len(v) for b, v in sorted(by_band.items())}, 'words_with_examples': len(ws_out)}
    with open(os.path.join(OUT, 'sentences-stats.json'), 'w') as f:
        json.dump(stats, f, indent=1)
    print(json.dumps(stats))


if __name__ == '__main__':
    main()
