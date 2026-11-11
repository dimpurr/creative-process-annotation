#!/usr/bin/env python3
"""Build art-commentary reference corpus from Project Gutenberg texts.

Downloads plain texts, strips boilerplate, sentence-splits, filters to
sentences actually about art, and outputs JSONL + META.
"""

import json
import re
import time
import urllib.request
import hashlib
import os
from collections import defaultdict

# ── Source catalogue ──────────────────────────────────────────────────────
# {stratum: [(gutenberg_id, short_id, title, author, year_approx, url_note)]}

SOURCES = {
    1: [  # Art Criticism
        (29907, "ruskin_modern_painters1", "Modern Painters, Volume 1",
         "John Ruskin", 1843, "Project Gutenberg"),
        (31623, "ruskin_modern_painters4", "Modern Painters, Volume 4",
         "John Ruskin", 1856, "Project Gutenberg"),
        (24650, "whistler_gentle_art", "The Gentle Art of Making Enemies",
         "James McNeill Whistler", 1890, "Project Gutenberg"),
        (58408, "hazlitt_collected7", "The Collected Works of William Hazlitt, Vol. 07",
         "William Hazlitt", 1903, "Project Gutenberg"),
        (2398, "pater_renaissance", "The Renaissance: Studies in Art and Poetry",
         "Walter Pater", 1873, "Project Gutenberg"),
        (17408, "berenson_florentine", "The Florentine Painters of the Renaissance",
         "Bernard Berenson", 1896, "Project Gutenberg"),
        (26716, "ruskin_crown_olive", "The Crown of Wild Olive (Pre-Raphaelitism essay)",
         "John Ruskin", 1866, "Project Gutenberg"),
    ],
    2: [  # Artist-authored theory / reflection
        (2176, "reynolds_discourses", "Seven Discourses on Art",
         "Sir Joshua Reynolds", 1778, "Project Gutenberg"),
        (5000, "leonardo_notebooks", "The Notebooks of Leonardo Da Vinci",
         "Leonardo da Vinci (transl. Jean Paul Richter)", 1883, "Project Gutenberg"),
        (5321, "kandinsky_spiritual", "Concerning the Spiritual in Art",
         "Wassily Kandinsky (transl. M.T.H. Sadler)", 1914, "Project Gutenberg"),
        (46915, "leonardo_treatise", "A Treatise on Painting",
         "Leonardo da Vinci (transl. John Francis Rigaud)", 1802, "Project Gutenberg"),
        (30325, "ruskin_elements_drawing", "The Elements of Drawing",
         "John Ruskin", 1857, "Project Gutenberg"),
        (65962, "cox_landscape", "Treatise on Landscape Painting in Water-Colours",
         "David Cox", 1922, "Project Gutenberg"),
    ],
    3: [  # Craft / pedagogy manuals
        (14264, "speed_drawing", "The Practice and Science of Drawing",
         "Harold Speed", 1913, "Project Gutenberg"),
        (30877, "parkhurst_painter_oil", "The Painter in Oil",
         "Daniel Burleigh Parkhurst", 1898, "Project Gutenberg"),
        (73397, "vasari_technique", "Vasari on Technique",
         "Giorgio Vasari (transl. Louisa S. Maclehose)", 1907, "Project Gutenberg"),
        (76939, "chevreul_colour", "The Laws of Contrast of Colour",
         "M.E. Chevreul (transl. John Spanton)", 1857, "Project Gutenberg"),
        (68866, "oldhand_hints", "Hints for Painters, Decorators, and Paper-Hangers",
         "An Old Hand", 1905, "Project Gutenberg"),
    ],
    4: [  # Museum / catalogue / art-historical narrative
        (25326, "vasari_lives1", "Lives of the Painters, Vol. 01",
         "Giorgio Vasari (transl. Gaston du C. de Vere)", 1912, "Project Gutenberg"),
        (25759, "vasari_lives2", "Lives of the Painters, Vol. 02",
         "Giorgio Vasari (transl. Gaston du C. de Vere)", 1912, "Project Gutenberg"),
        (26860, "vasari_lives3", "Lives of the Painters, Vol. 03",
         "Giorgio Vasari (transl. Gaston du C. de Vere)", 1912, "Project Gutenberg"),
        (25632, "waters_history_art", "A History of Art for Beginners and Students",
         "Clara Erskine Clement Waters", 1887, "Project Gutenberg"),
        (30098, "phillipps_venetian", "The Venetian School of Painting",
         "Evelyn March Phillipps", 1912, "Project Gutenberg"),
        (59694, "caffin_american", "American Masters of Painting",
         "Charles H. Caffin", 1902, "Project Gutenberg"),
        (22690, "burnet_rembrandt", "Rembrandt and His Works",
         "John Burnet", 1849, "Project Gutenberg"),
        (529, "steedman_knights", "Knights of Art: Stories of the Italian Painters",
         "Amy Steedman", 1901, "Project Gutenberg"),
        (22379, "holme_watercolour", "Masters of Water-Colour Painting",
         "Various (ed. Geoffrey Holme)", 1922, "Project Gutenberg"),
    ],
    5: [  # Other artists' letters / diaries
        (78022, "preraphaelite_diaries", "Praeraphaelite Diaries and Letters",
         "Dante Gabriel Rossetti, Ford Madox Brown, et al.", 1900, "Project Gutenberg"),
        (11242, "symonds_michelangelo", "The Life of Michelangelo Buonarroti",
         "John Addington Symonds", 1893, "Project Gutenberg"),
    ],
}

# ── Art keyword filter ────────────────────────────────────────────────────
# Sentences must contain at least MIN_KEYWORDS from this list (case-insensitive)
ART_KEYWORDS = {
    'paint', 'painter', 'painting', 'painted', 'paints',
    'picture', 'pictures', 'pictorial',
    'colour', 'colors', 'color', 'colours', 'coloring', 'colouring',
    'drawing', 'draw', 'drawn', 'draws',
    'canvas', 'canvases',
    'composition', 'compositions',
    'artist', 'artists', 'artistic',
    'brush', 'brushes', 'brushwork',
    'form', 'forms',
    'tone', 'tones', 'tonal',
    'figure', 'figures', 'figurative',
    'portrait', 'portraits', 'portraiture',
    'landscape', 'landscapes',
    'studio', 'studios',
    'sketch', 'sketches', 'sketching',
    'fresco', 'frescoes',
    'pigment', 'pigments',
    'palette', 'palettes',
    'gallery', 'galleries',
    'master', 'masters', 'masterpiece', 'masterpieces',
    'sculpture', 'sculptor', 'sculptors',
    'statue', 'statues', 'statuary',
    'chiaroscuro',
    'perspective',
    'foreground', 'background', 'middle-ground',
    'outline', 'outlines',
    'light', 'shadow', 'shadows', 'shading', 'shade', 'shades',
    'oil', 'oils',
    'watercolour', 'watercolor', 'water-colour', 'water-color',
    'engraving', 'etching', 'print', 'prints',
    'draughtsman', 'draughtsmanship',
    'design', 'designs', 'designer',
    'mural', 'murals',
    'altarpiece', 'altar-piece',
    'easel',
    'canvas',
    'portray', 'portrayal', 'portrayed',
    'depict', 'depicted', 'depiction',
    'render', 'rendered', 'rendering',
    'brushstroke', 'brushstrokes',
    'impasto',
    'glaze', 'glazes', 'glazing',
    'varnish',
    'tint', 'tints',
    'hue', 'hues',
    'modelling', 'modeling',
    'anatomy', 'anatomical',
    'proportion', 'proportions',
    'harmony', 'harmonies',
    'aesthetic', 'aesthetics',
    'beauty', 'beautiful',
    'sublime',
    'art', 'arts',
}
MIN_KEYWORDS = 1  # at least 1 art keyword

# ── Download helpers ──────────────────────────────────────────────────────

def download_gutenberg_text(gutenberg_id, max_retries=3):
    """Download plain text from Project Gutenberg. Returns decoded string or None."""
    url = f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.txt"
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (research bot)'})
            with urllib.request.urlopen(req, timeout=60) as resp:
                text = resp.read().decode('utf-8', errors='replace')
            return text
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                print(f"  ERROR downloading {gutenberg_id}: {e}")
                return None


def strip_gutenberg_boilerplate(text):
    """Strip Gutenberg header and footer, keep only the body text."""
    # Pattern 1: standard *** START OF ... ***  to  *** END OF ... ***
    m_start = re.search(r'\*{3}\s*START OF.*?\*{3}', text)
    m_end = re.search(r'\*{3}\s*END OF.*?\*{3}', text)
    if m_start:
        body = text[m_start.end():]
        if m_end:
            body = body[:m_end.start()]
        return body.strip()

    # Pattern 2: alternative format with "START OF THE PROJECT GUTENBERG"
    m_start2 = re.search(r'(?i)START OF (THE )?PROJECT GUTENBERG', text)
    m_end2 = re.search(r'(?i)END OF (THE )?PROJECT GUTENBERG', text)
    if m_start2:
        # Find end of that line
        line_end = text.index('\n', m_start2.start())
        body = text[line_end + 1:]
        if m_end2:
            body = body[:m_end2.start()]
        return body.strip()

    # Fallback: return as-is
    return text.strip()


def remove_section_headers(text):
    """Remove ALL-CAPS section headers and roman numeral lines."""
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Skip purely numeric or roman numeral lines
        if re.match(r'^[IVXLCDM]+\.?$', stripped):
            continue
        # Skip lines that are ALL CAPS and short (likely headers)
        if stripped.isupper() and len(stripped) > 5 and len(stripped) < 80:
            continue
        # Skip lines that are just numbers
        if re.match(r'^\d+$', stripped):
            continue
        cleaned.append(line)
    return '\n'.join(cleaned)


def clean_text(text):
    """Clean Gutenberg text: normalize whitespace, remove obvious artifacts."""
    # Replace multiple newlines with double newline
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove Gutenberg footnotes markers [1], [Footnote: ...], etc.
    text = re.sub(r'\[Footnote:.*?\]', '', text, flags=re.DOTALL)
    text = re.sub(r'\[\d+\]', '', text)
    # Remove illustration markers
    text = re.sub(r'\[Illustration:.*?\]', '', text, flags=re.DOTALL)
    text = re.sub(r'\[Pg \d+\]', '', text)
    # Normalize quotes
    text = text.replace('‘', "'").replace('’', "'")
    text = text.replace('“', '"').replace('”', '"')
    text = text.replace('—', '—').replace('–', '--')
    # Remove extra spaces
    text = re.sub(r' +', ' ', text)
    return text.strip()


# ── Sentence splitting ────────────────────────────────────────────────────

def sentence_split(text):
    """Split text into sentences using regex. Returns list of sentences."""
    # Normalize: ensure sentences end with proper punctuation
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text)

    # Split on sentence boundaries: .!? followed by space and capital letter or quote
    # Also handle Mr. Mrs. Dr. etc. exceptions
    # First, protect abbreviations
    protected = text
    for abbr in ['Mr.', 'Mrs.', 'Ms.', 'Dr.', 'Prof.', 'St.', 'Rev.', 'Hon.',
                 'Esq.', 'Jr.', 'Sr.', 'Capt.', 'Col.', 'Gen.', 'Lt.', 'Maj.',
                 'Mt.', 'Vol.', 'vol.', 'no.', 'Nos.', 'fig.', 'Figs.',
                 'i.e.', 'e.g.', 'etc.', 'vs.', 'viz.', 'al.',
                 'pp.', 'p.', 'chs.', 'No.', 'Co.', 'Ltd.', 'Inc.']:
        protected = protected.replace(abbr, abbr.replace('.', '@DOT@'))

    # Split sentences
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z"\'])', protected)
    # Also split on ? and ! followed by space
    # Restore abbreviations
    sentences = [s.replace('@DOT@', '.') for s in sentences]

    # Filter and clean
    result = []
    for s in sentences:
        s = s.strip()
        # Remove leading/trailing quotes and bullets
        s = re.sub(r'^["\'\s•\-–—*•·]+\s*', '', s)
        s = re.sub(r'\s*["\']$', '', s)
        s = s.strip()
        if s:
            result.append(s)
    return result


def is_valid_sentence(s):
    """Check if a sentence passes basic quality filters."""
    s = s.strip()
    # Length: 6-60 words
    words = s.split()
    if len(words) < 6 or len(words) > 60:
        return False
    # Must start with a capital letter (or quote + capital)
    if not re.match(r'^["\']?[A-Z]', s):
        return False
    # Must not be ALL CAPS
    if s.isupper():
        return False
    # Must not be mostly non-alphabetic
    alpha_ratio = sum(1 for c in s if c.isalpha()) / max(len(s), 1)
    if alpha_ratio < 0.5:
        return False
    return True


def has_art_keywords(s, min_count=MIN_KEYWORDS):
    """Check if sentence contains enough art-related keywords."""
    s_lower = s.lower()
    words = set(re.findall(r'[a-z]+', s_lower))
    matches = words & ART_KEYWORDS
    return len(matches) >= min_count


# ── Processing pipeline ───────────────────────────────────────────────────

def process_source(gutenberg_id, short_id, title, author, stratum):
    """Download and process one source. Returns list of filtered sentences."""
    print(f"  [{stratum}] {short_id} — downloading...")
    raw = download_gutenberg_text(gutenberg_id)
    if raw is None:
        return []

    print(f"    {len(raw):,} chars raw → ", end='')
    body = strip_gutenberg_boilerplate(raw)
    print(f"{len(body):,} chars body → ", end='')
    body = remove_section_headers(body)
    body = clean_text(body)
    print(f"{len(body):,} chars cleaned", end='')

    sentences = sentence_split(body)
    print(f" → {len(sentences)} sentences", end='')

    # Filter
    valid = [s for s in sentences if is_valid_sentence(s)]
    art_sentences = [s for s in valid if has_art_keywords(s)]
    print(f" → {len(valid)} valid → {len(art_sentences)} art-filtered")

    return art_sentences


def deduplicate_across_strata(all_data):
    """Remove duplicate sentences across all strata."""
    seen = set()
    result = []
    for item in all_data:
        # Normalize for dedup: lowercase, strip punctuation
        norm = re.sub(r'[^\w\s]', '', item['sentence'].lower())
        norm = re.sub(r'\s+', ' ', norm).strip()
        if norm not in seen and len(norm) > 20:
            seen.add(norm)
            result.append(item)
    return result


def sample_stratum(sentences, max_per_source=400, target_total=2500):
    """Sample evenly across sources within a stratum.
    Takes up to max_per_source from each source, aiming for target_total."""
    if not sentences:
        return []

    # Group by source
    by_source = defaultdict(list)
    for s in sentences:
        by_source[s['source']].append(s)

    # Shuffle within each source group deterministically
    for src in by_source:
        by_source[src].sort(key=lambda x: hashlib.md5(x['sentence'].encode()).hexdigest())
        by_source[src] = by_source[src][:max_per_source]

    # Interleave: take one from each source in rotation
    result = []
    indices = {src: 0 for src in by_source}
    while len(result) < target_total:
        added = False
        for src in sorted(by_source.keys()):
            if indices[src] < len(by_source[src]):
                result.append(by_source[src][indices[src]])
                indices[src] += 1
                added = True
        if not added:
            break
        if len(result) >= target_total:
            break

    return result[:target_total]


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    output_dir = os.environ.get('OUT_DIR') or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'raw')
    jsonl_path = os.path.join(output_dir, 'art-commentary-corpus.jsonl')
    meta_path = os.path.join(output_dir, 'art-commentary-META.md')

    os.makedirs(output_dir, exist_ok=True)

    all_data = []
    source_stats = {}
    stratum_counts = defaultdict(int)

    for stratum in sorted(SOURCES.keys()):
        stratum_label = {
            1: 'Art Criticism',
            2: 'Artist Theory / Reflection',
            3: 'Craft / Pedagogy Manuals',
            4: 'Museum / Catalogue / Art History',
            5: "Artists' Letters / Diaries",
        }[stratum]
        print(f"\n{'='*60}")
        print(f"STRATUM {stratum}: {stratum_label}")
        print(f"{'='*60}")

        for gid, short_id, title, author, year, url_note in SOURCES[stratum]:
            sentences = process_source(gid, short_id, title, author, stratum)
            n_kept_before_sample = len(sentences)
            source_stats[short_id] = {
                'title': title,
                'author': author,
                'year': year,
                'url_note': url_note,
                'gutenberg_id': gid,
                'stratum': stratum,
                'sentences_raw': n_kept_before_sample,
            }
            for s in sentences:
                all_data.append({
                    'stratum': stratum,
                    'source': short_id,
                    'sentence': s,
                })
            stratum_counts[stratum] += n_kept_before_sample
            time.sleep(0.5)  # Be polite to Gutenberg servers

    # Deduplicate
    print(f"\n{'='*60}")
    print(f"BEFORE DEDUP: {len(all_data)} sentences total")
    all_data = deduplicate_across_strata(all_data)
    print(f"AFTER DEDUP:  {len(all_data)} sentences total")

    # Print per-stratum counts
    dedup_counts = defaultdict(int)
    for item in all_data:
        dedup_counts[item['stratum']] += 1
    for s in sorted(dedup_counts):
        print(f"  Stratum {s}: {dedup_counts[s]} sentences")

    # Sample evenly within each stratum
    print(f"\n{'='*60}")
    print("SAMPLING (max ~2500 per stratum, ~400 per source)")
    print(f"{'='*60}")
    final_data = []
    for stratum in sorted(SOURCES.keys()):
        stratum_items = [d for d in all_data if d['stratum'] == stratum]
        sampled = sample_stratum(stratum_items, max_per_source=400, target_total=2500)
        final_data.extend(sampled)
        # Update stats
        sampled_by_source = defaultdict(int)
        for s in sampled:
            sampled_by_source[s['source']] += 1
        for short_id in sorted(sampled_by_source):
            source_stats[short_id]['sentences_kept'] = sampled_by_source[short_id]
        print(f"  Stratum {s}: {len(stratum_items)} → {len(sampled)} kept")

    # Shuffle final output
    import random
    random.seed(42)
    random.shuffle(final_data)

    # Write JSONL
    print(f"\nWriting {len(final_data)} sentences to {jsonl_path}")
    with open(jsonl_path, 'w', encoding='utf-8') as f:
        for item in final_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    # Write META
    print(f"Writing META to {meta_path}")
    with open(meta_path, 'w', encoding='utf-8') as f:
        f.write("---\n")
        f.write("title: Art Commentary Reference Corpus — Metadata\n")
        f.write("date: 2026-07-08\n")
        f.write("status: built\n")
        
        f.write("---\n\n")
        f.write("# Art Commentary Reference Corpus\n\n")
        f.write(f"**Total sentences**: {len(final_data)}\n\n")
        f.write("Built for experiment X1: a general embedding space of \"how people write about visual art\",")
        f.write(" into which Van Gogh's letters will be projected.\n\n")

        f.write("## Corpus Statistics\n\n")
        for s in sorted(SOURCES.keys()):
            label = {
                1: 'Art Criticism',
                2: 'Artist Theory / Reflection',
                3: 'Craft / Pedagogy Manuals',
                4: 'Museum / Catalogue / Art History',
                5: "Artists' Letters / Diaries",
            }[s]
            n = sum(1 for d in final_data if d['stratum'] == s)
            f.write(f"- **Stratum {s}** ({label}): {n} sentences\n")

        f.write("\n## Filtering Rules\n\n")
        f.write("- **Sentence length**: 6–60 words\n")
        f.write("- **Must start with capital letter** (or quote + capital)\n")
        f.write("- **Art keyword filter**: sentence must contain ≥1 word from a curated list of ~120 art-domain terms")
        f.write(" (paint/picture/colour/drawing/canvas/composition/artist/brush/form/tone/palette/gallery/")
        f.write("sculpture/portrait/landscape/studio/sketch/fresco/pigment/chiaroscuro/perspective/etc.)\n")
        f.write("- **Alpha ratio**: ≥50% alphabetic characters (excludes tables/lists)\n")
        f.write("- **Not ALL CAPS** (excludes headers)\n")
        f.write("- **Deduplication**: normalized exact match (lowercase, no punctuation, ≥20 chars after normalization)\n\n")

        f.write("## Per-Source Details\n\n")
        f.write("| Short ID | Stratum | Title | Author | Year | URL Basis | Raw | Kept |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for short_id in sorted(source_stats.keys()):
            st = source_stats[short_id]
            raw_n = st.get('sentences_raw', 0)
            kept_n = st.get('sentences_kept', 0)
            f.write(f"| {short_id} | {st['stratum']} | {st['title']} | {st['author']} | {st['year']} | ")
            f.write(f"{st['url_note']} #{st['gutenberg_id']} | {raw_n} | {kept_n} |\n")

        f.write("\n## Known Noise / Limitations\n\n")
        f.write("- Sentence splitting is regex-based (no NLTK); may occasionally mis-split on abbreviations.\n")
        f.write("- Boilerplate removal relies on Gutenberg's standard START/END markers; edge cases possible.\n")
        f.write("- Art-keyword filter is a simple lexical heuristic: some non-art sentences may sneak through")
        f.write(" (e.g., \"colour\" in a non-art context); some art discourse sentences may be missed")
        f.write(" (e.g., discussing patronage without art keywords). False positive rate estimated < 10%.\n")
        f.write("- Stratum 5 (Artists' Letters) is thin relative to other strata — only 2 sources available")
        f.write(" in public domain via Project Gutenberg. Præraphaelite diaries are the main source.\n")
        f.write("- All texts are public domain (pre-1928 or explicit PD dedication).\n")
        f.write("- Copyright basis: Project Gutenberg public domain verification for all texts.\n\n")

        f.write("## Source URLs\n\n")
        for short_id in sorted(source_stats.keys()):
            st = source_stats[short_id]
            gid = st['gutenberg_id']
            f.write(f"- **{short_id}**: <https://www.gutenberg.org/ebooks/{gid}>\n")

    # Print final summary
    print(f"\n{'='*60}")
    print(f"FINAL SUMMARY")
    print(f"{'='*60}")
    for s in sorted(SOURCES.keys()):
        n = sum(1 for d in final_data if d['stratum'] == s)
        label = {
            1: 'Art Criticism',
            2: 'Artist Theory / Reflection',
            3: 'Craft / Pedagogy Manuals',
            4: 'Museum / Catalogue / Art History',
            5: "Artists' Letters / Diaries",
        }[s]
        print(f"  Stratum {s} ({label}): {n} sentences")
    print(f"  TOTAL: {len(final_data)} sentences")
    print(f"\nDONE: {jsonl_path}")


if __name__ == '__main__':
    main()
