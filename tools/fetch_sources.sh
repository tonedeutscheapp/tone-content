#!/usr/bin/env bash
# Downloads the open-licence sources into data/raw (runs in GitHub Actions).
set -euo pipefail
R=${1:-data/raw}; mkdir -p "$R"; cd "$R"
get() { curl -fsSL --retry 4 --retry-delay 5 -o "$2" "$1"; }

[ -s dewiktionary.jsonl.gz ] || get https://kaikki.org/dewiktionary/raw-wiktextract-data.jsonl.gz dewiktionary.jsonl.gz
[ -s de_50k.txt ] || get https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/de/de_50k.txt de_50k.txt

T=https://downloads.tatoeba.org/exports/per_language
for l in deu tur eng; do
  [ -s ${l}_sentences.tsv ] || { get $T/$l/${l}_sentences.tsv.bz2 $l.bz2 && bunzip2 -c $l.bz2 > ${l}_sentences.tsv && rm $l.bz2; }
done
need_full=0
for p in tur eng; do
  [ -s deu-${p}_links.tsv ] && continue
  if get $T/deu/deu-${p}_links.tsv.bz2 l.bz2; then bunzip2 -c l.bz2 > deu-${p}_links.tsv; rm l.bz2; else need_full=1; fi
done
if [ $need_full = 1 ]; then
  # fallback: full link table, filtered to German-Turkish / German-English pairs
  get https://downloads.tatoeba.org/exports/links.tar.bz2 links.tar.bz2
  tar -xjf links.tar.bz2 && rm links.tar.bz2
  python3 - <<'EOF'
de = {l.split('\t')[0] for l in open('deu_sentences.tsv', encoding='utf-8')}
for p in ('tur', 'eng'):
    ids = {l.split('\t')[0] for l in open(f'{p}_sentences.tsv', encoding='utf-8')}
    with open(f'deu-{p}_links.tsv', 'w') as o:
        for l in open('links.csv'):
            a, _, b = l.strip().partition('\t')
            if a in de and b in ids: o.write(f'{a}\t{b}\n')
EOF
  rm -f links.csv
fi
ls -la
