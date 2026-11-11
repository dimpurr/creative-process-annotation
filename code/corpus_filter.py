"""The admission test a sentence has to pass to enter the annotation corpus.

The screening step applies this filter to the sentence pool before model annotation.
The release step also applies it to `corpus_public.jsonl`.

The criteria are shape only. Nothing here judges what a sentence is about; that is the
screening model's job and this runs before it.

  truncated       ends on an abbreviation whose continuation was lost
  head fragment   begins with the tail of a reference, "47] and the Concerto ..."
  lower start     begins mid-sentence
  no terminator   ends without sentence-final punctuation
  catalogue       carries a catalogue-raisonne or cross-reference marker
  shout           set entirely in capitals, which in these editions means a letterhead
  too short       under 25 characters, which in practice is an address line

YMSM is the Whistler catalogue raisonne, published in 1980. Whistler died in 1903, so a
sentence carrying that marker is editorial without exception.
"""
import re

MIN_CHARS = 25

ABBREV = (r"No|Nos|Op|Vol|Vols|p|pp|Ch|Fig|Figs|Pl|Bk|Mr|Mrs|Ms|Dr|Prof|Rev|Capt|Col|Gen"
          r"|Hon|Esq|Jr|Sr|St|Messrs|Lt|Sgt|M|MM|Mme|Mlle|Mgr|Hr|Fr|Frl|etc|viz|cf|vs|ca")

TRUNCATED = re.compile(r"(?:^|[\s\[(])(" + ABBREV + r")\.$")
HEAD_FRAGMENT = re.compile(r"^\s*\d+\s*[\]\)]")
LOWER_START = re.compile(r"^\s*[a-z]")
TERMINATOR = re.compile(r"[.!?\"'’”)\]]$")
CATALOGUE = re.compile(r"\bYMSM\b|\bGUW\b|\[more\]|#\d{3,}|\bto JW\b")


def reject(sentence, mode="sentence"):
    """Return the name of the first criterion the sentence fails, or None if it passes.

    Van Gogh comes through the identifier route, where a row is the passage the editors
    marked as referring to a work, not a sentence, so two of the tests do not apply to it
    and `mode="passage"` drops them:

      too_short       "Fields in winter." is seventeen characters and is the whole point
                      of the row, which is that it names a work
      no_terminator   a passage can end on a colon or a dash and still be complete

    The tests that survive are the ones about a row starting or ending in the middle of
    something, which is a defect whatever the unit is.
    """
    s = sentence.strip()
    passage = mode == "passage"
    if not s:
        return "empty"
    if not passage and len(s) < MIN_CHARS:
        return "too_short"
    if s.isupper():
        return "shout"
    if CATALOGUE.search(s):
        return "catalogue"
    if TRUNCATED.search(s):
        return "truncated"
    if HEAD_FRAGMENT.match(s):
        return "head_fragment"
    if LOWER_START.match(s):
        return "lower_start"
    if not passage and not TERMINATOR.search(s):
        return "no_terminator"
    return None


def apply(items, key="sentence", dedupe=True, mode="sentence"):
    """Filter a list of dicts. Returns (kept, counts).

    Duplicates are dropped after the shape tests, keeping the first occurrence. A string
    that appears fifteen times is fifteen identical annotation units, which costs fifteen
    times as much and inflates agreement between any two annotators that see it.
    """
    import collections
    kept, counts, seen = [], collections.Counter(), set()
    for it in items:
        s = it[key] if isinstance(it, dict) else it
        why = reject(s, mode)
        if why:
            counts[why] += 1
            continue
        if dedupe:
            n = re.sub(r"\s+", " ", s.strip())
            if n in seen:
                counts["duplicate"] += 1
                continue
            seen.add(n)
        kept.append(it)
    return kept, counts
