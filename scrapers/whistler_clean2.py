#!/usr/bin/env python3
"""Second cleaning pass over the Whistler letters.

The first pass removes editorial apparatus sentence by sentence. This one works at the level
of the letter: catalogue tails, envelope and postmark blocks, translation notes, publication
records and press cuttings tend to sit at the end of a record in a block, and a rule that
cuts from a boundary removes them better than a sentence filter can.

It also drops records that are entirely editorial, and tidies inline leftovers:
page markers, trailing date brackets, stray editorial phrases.

Input:  whistler_JW_letters_CLEAN.jsonl   (body_clean, from the first pass)
Output: whistler_JW_letters_CLEAN2.jsonl  (adds body_clean2)

The sentence pool used for screening is produced from body_clean2, not body_clean. Splitting
the wrong field gives a pool roughly twice the size with only partial overlap.
"""
import json, os, re, random
from collections import Counter
from pathlib import Path

REPO   = Path(__file__).resolve().parent.parent
RAW    = Path(os.environ.get("WHISTLER_RAW") or (REPO / "data" / "raw" / "whistler"))

INPUT  = RAW / "whistler_JW_letters_CLEAN.jsonl"
OUTPUT = RAW / "whistler_JW_letters_CLEAN2.jsonl"
REPORT = RAW / "whistler_CLEAN2_report.md"

random.seed(42)

with open(INPUT) as f:
    all_records = [json.loads(l) for l in f]

letter_types = {
    'Letter', 'Letter copy', 'Letter draft', 'Published Letter',
    'Telegram', 'Telegram copy', 'Telegram draft',
    'Letter draft or copy', 'Letter copy or draft', 'Letter copy & draft',
    'Letter drafts', 'Letter copies', 'letter', 'Letter Published',
    'Published Letter copy', 'Published letter', 'Published telegram',
    'Letter fragment', 'Letter incomplete', 'Letter and lecture draft',
}

focus = [r for r in all_records if r['doctype'] in letter_types]
print(f"Letter-type: {len(focus)}")

# ═══════════════════════════════════════════════════════════
# BOUNDARY DETECTION
# ═══════════════════════════════════════════════════════════

def find_boundary(text):
    boundaries = []
    
    # A: Copyright
    m = re.search(r'This document is protected by copyright\.', text, re.IGNORECASE)
    if m:
        boundaries.append((m.start(), 'R_copyright'))
    
    # B: Envelope:
    for m in re.finditer(r'\bEnvelope:', text):
        after = text[m.end():m.end()+50].strip()
        if re.match(r'(?:Notes:|To\s|\[|Immediate|Recommande|\d)', after, re.IGNORECASE):
            boundaries.append((m.start(), 'R_envelope'))
            break
    
    # C: Notes:
    for m in re.finditer(r'\bNotes:', text):
        after = text[m.end():m.end()+100].strip()
        if re.match(r'\d+\.\s*(?:\d{4}|[A-Z])', after) or 'Dated' in after[:200]:
            boundaries.append((m.start(), 'R_notes'))
            break
    
    # D: Dated from/by / Date received (lower threshold if no copyright)
    has_cr = 'protected by copyright' in text.lower()
    threshold = 0.6 if has_cr else 0.3
    for m in re.finditer(r'(?:[Dd]ated (?:from|by)|Date (?:received|of publication|of receipt))\b', text):
        if m.start() > len(text) * threshold:
            boundaries.append((m.start(), 'R_dated'))
            break
    
    # E: Translation:
    for m in re.finditer(r'\bTranslation:', text):
        if m.start() > len(text) * 0.2:
            boundaries.append((m.start(), 'R_translation'))
            break
    
    # F: Published in
    for m in re.finditer(r'[Pp]ublished in\b', text):
        if m.start() > len(text) * 0.4:
            boundaries.append((m.start(), 'R_published_in'))
            break
    
    # G: Reproduced
    for m in re.finditer(r'[Rr]eproduced (?:in|from)\b', text):
        if m.start() > len(text) * 0.4:
            boundaries.append((m.start(), 'R_reproduced'))
            break
    
    # H: Catalog notations
    for m in re.finditer(r'\b(?:ALS|TLfc|PLfc|MsLc|PLc|PD/MsS)\b', text):
        if m.start() > len(text) * 0.5:
            boundaries.append((m.start(), 'R_catalog'))
            break
    
    # I: Press-cutting
    for m in re.finditer(r'[Pp]ress[ -]?cutting\]?', text):
        if m.start() > len(text) * 0.3:
            boundaries.append((m.start(), 'R_press'))
            break
    
    # J: Manuscript/physical notes
    for pat in [r'Copied in an unknown hand', r'Transcribed by\b',
                r'Written in another hand', r'written in another hand',
                r'The letter has not been located', r'The original has not been',
                r'written at right.angles to', r'This side of the paper',
                r'no article signed by', r'Date of (?:publication|receipt)',
                r'printed form', r'Note written in another hand',
                r'This document is protected',
                r'The (?:letter|envelope|paper) (?:is|has|was)']:
        for m in re.finditer(pat, text, re.IGNORECASE):
            if m.start() > len(text) * 0.4:
                boundaries.append((m.start(), 'R_ms_note'))
                break
    
    # K: Biographical parenthetical
    for m in re.finditer(r'\b[A-Z]\w+ [A-Z]\w+ \((?:b\.|d\.|fl\.|m\.)\s*\d{4}', text):
        if m.start() > len(text) * 0.5:
            boundaries.append((m.start(), 'R_bio'))
            break
    
    if not boundaries:
        return len(text), None
    boundaries.sort()
    return boundaries[0]


# ═══════════════════════════════════════════════════════════
# ENTIRELY EDITORIAL
# ═══════════════════════════════════════════════════════════

EDITORIAL_ONLY_STARTS = [
    r'^[Aa]lternatively it could',
    r'^[Tt]his (?:appears to be|is possibly|letter concerns|letter could|is a)',
    r'^[Ii]t is (?:described|listed|recorded|advertised|not|possible)',
    r'^[Nn]o (?:article|further|copy)',
    r'^(?:ALS|TLfc|PLfc|MsLc|PLc|PD/MsS|PLf/TLc)\b',
    r'^[Pp]ublished in\b',
    r'^(?:Copied|Transcribed) (?:in|by)',
    r'^[Tt]he (?:letter|original|document|manuscript|diary)',
    r'^(?:Probably|Possibly|Perhaps)\b.*(?:could|might|may)\b',
    r'^[Dd]ated (?:from|by)\b',
]

def is_entirely_editorial(text):
    """Detect records that have NO letter content at all."""
    t = text.strip()
    if len(t) < 20:
        return False
    
    # If it has letter structure → not entirely editorial
    if re.search(r'\b(?:Dear|My dear|Cher|Mon cher|Ma ch[eè]re|Sir\b|Gentlemen)', t, re.IGNORECASE):
        return False
    if re.search(r'\b(?:Yours|Sincerely|Always|Affectionately|Very truly|Ever|Faithfully)\b', t, re.IGNORECASE):
        return False
    if re.search(r'\bJ\.?\s*(?:McN|Whistler|McNeill)?\b', t, re.IGNORECASE):
        return False
    
    # Check if it starts with a known editorial-only pattern
    for pat in EDITORIAL_ONLY_STARTS:
        if re.match(pat, t, re.IGNORECASE):
            return True
    
    return False


# ═══════════════════════════════════════════════════════════
# INLINE CLEANUP
# ═══════════════════════════════════════════════════════════

def clean_within_text(text):
    stats = {}
    
    # Remove [p.] markers
    before = text
    text = re.sub(r'\[p\.\s*', '', text)
    stats['inline_[p.]'] = len(before) - len(text)
    
    # Remove trailing date brackets: "December 1867]", "1867]", "1896/1899]"
    before = text
    text = re.sub(r'\n?\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*\d{4}[\/\d]*\]\s*$', '', text)
    text = re.sub(r'\n?\s*\d{4}[\/\d]*\]\s*$', '', text)
    # Bare month+year at end: "January 1879"
    text = re.sub(r'\n?\s*(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\s*$', '', text)
    stats['inline_date_end'] = len(before) - len(text)
    
    # Remove trailing editorial phrases
    before = text
    trail_pats = [
        r'\n?\s*[Dd]ated (?:from|by)\b[^\n]*$',
        r'\n?\s*Date (?:received|of publication|of receipt)\b[^\n]*$',
        r'\n?\s*[Pp]ublished in\b[^\n]*$',
        r'\n?\s*[Rr]eproduced (?:in|from)\b[^\n]*$',
        r'\n?\s*(?:Copied|Transcribed) (?:in|by)[^\n]*$',
        r'\n?\s*Written in another hand[^\n]*$',
        r'\n?\s*The (?:letter|original|document|manuscript) has not been[^\n]*$',
        r'\n?\s*(?:Answer|Note) (?:This is|written in|added in)[^\n]*$',
        r'\n?\s*[A-Z]\w+ [A-Z]\w+ \((?:b\.|d\.|fl\.|m\.)[^\n]*$',
    ]
    for pat in trail_pats:
        text = re.sub(pat, '', text)
    stats['inline_trail_ed'] = len(before) - len(text)
    
    # Whitespace
    before = text
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    stats['inline_ws'] = len(before) - len(text)
    
    return text, stats


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

output_records = []
all_stats = []
rule_tracker = Counter()
entirely_ed = []

for r in all_records:
    out = dict(r)
    body = r.get('body_clean', '')
    
    if r['doctype'] in letter_types and body.strip():
        original_len = len(body)
        
        if is_entirely_editorial(body):
            out['body_clean2'] = ''
            entirely_ed.append(r['cid'])
            all_stats.append({
                'cid': r['cid'], 'doctype': r['doctype'],
                'chars_before': original_len, 'chars_after': 0,
                'chars_removed': original_len,
                'boundary_rule': 'R_all_editorial',
            })
            rule_tracker['R_all_editorial'] += 1
        else:
            cut_pos, rule = find_boundary(body)
            if rule:
                rule_tracker[rule] += 1
                text = body[:cut_pos].rstrip()
            else:
                text = body
            
            text, _ = clean_within_text(text)
            
            out['body_clean2'] = text
            all_stats.append({
                'cid': r['cid'], 'doctype': r['doctype'],
                'chars_before': original_len, 'chars_after': len(text),
                'chars_removed': original_len - len(text),
                'boundary_rule': rule,
            })
    else:
        out['body_clean2'] = body
    
    output_records.append(out)

with open(OUTPUT, 'w') as f:
    for r in output_records:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')

total_before = sum(s['chars_before'] for s in all_stats)
total_after = sum(s['chars_after'] for s in all_stats)

print(f"\n=== SUMMARY ===")
print(f"Removed: {total_before-total_after:,} ({(total_before-total_after)/total_before*100:.1f}%)")
print(f"Cleaned: {sum(1 for s in all_stats if s['chars_removed'] > 0)}, Unchanged: {sum(1 for s in all_stats if s['chars_removed'] == 0)}")
print(f"Entirely editorial: {len(entirely_ed)}")
print(f"Rules: {rule_tracker.most_common()}")

# Check issues
for cid in ['9195', '8758', '849', '4186', '8769', '7136']:
    for r in output_records:
        if r['cid'] == cid:
            bc2 = r.get('body_clean2', '')
            print(f"cid={cid}: len={len(bc2)}, ends: ...{bc2[-120:] if bc2 else '(EMPTY)'}")

print(f"\nOutput: {OUTPUT}")
