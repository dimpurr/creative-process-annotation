#!/usr/bin/env python3
"""Remove the editions' footnotes from the Beethoven and Mozart letters.

The earlier pass works one unit at a time:

    FOOTNOTE_LINE = re.compile(r'^\\s*\\[Footnote\\b')       # unit opens a footnote: drop it
    FOOTNOTE_FRAG = re.compile(r'\\[Footnote\\b[^\\]]*\\]?')   # otherwise cut to the first ]

Both rules can only see inside the unit they are given, and a footnote in these editions
does not fit in one unit. It opens in one, runs through several more, and closes in a
later one. The first rule drops the unit that opens it and the rest of the footnote stays
in the letter. One Beethoven letter ends up as four sentences by
Beethoven followed by twelve by his editors, all of it one record:

    [3] I very much doubt whether I shall be able to present myself at Y.R.H.'s ...
    [4] January-February.]
    [5] 114), and a second concert that he had projected does not appear to have ...
    [10] Thayer states that it was written by Beethoven in 1810, and sold to ...

That residue is about four per cent of the text and about ten per cent of the screened
corpus, because a footnote is mostly talk about particular works and the screening step
selects for exactly that. The editors' voice is therefore concentrated by every step that
follows it.

This pass tracks bracket depth across units instead. A footnote begins at a unit opening
with `[Footnote` and ends where the brackets balance again, however many units later that
is. Everything between goes. The other rules are unchanged.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WORK = os.environ.get("WORK_DIR") or os.path.join(REPO, "data", "work")
SRC = os.path.join(WORK, "parsed")
OUT = os.path.join(WORK, "parsed")

FOOTNOTE = re.compile(r"\[Footnote\b", re.I)
BARE_MARKER = re.compile(r"\[\d{1,3}\]")
ADDR_HEAD = re.compile(r"^\s*TO [A-Z][A-Z\s,.'&-]{2,}?\.(\[\d+\])?\s*")
ITALIC = re.compile(r"_([^_\n]{1,60})_")
GUTENBERG = re.compile(r"Project Gutenberg|General Terms of Use|copyright law|\bdonations\b"
                       r"|\bEBOOK\b|electronic works?\b", re.I)
ORPHAN_TAIL = re.compile(r"^[^\[\]]{0,60}\]\s*")


def cut_footnotes(text):
    """Remove every [Footnote ...] span, matching brackets so nesting is handled.

    The units the letters arrive in do not line up with the footnotes: a footnote can open
    in the middle of a unit and close several units later. Working on the joined text is
    the only way to see where one ends.
    """
    out, i, removed = [], 0, 0
    while True:
        m = FOOTNOTE.search(text, i)
        if not m:
            out.append(text[i:])
            break
        out.append(text[i:m.start()])
        depth, j = 0, m.start()
        while j < len(text):
            if text[j] == "[":
                depth += 1
            elif text[j] == "]":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        removed += j - m.start()
        i = j
    return "".join(out), removed


def strip_letter(units):
    text = " ".join(u.strip() for u in units if u.strip())
    text, removed = cut_footnotes(text)
    # a bracket left over from a footnote that opened before this letter began
    text = ORPHAN_TAIL.sub("", text, count=1)
    # and a bracket left dangling at the end, whose opening the parser did not keep
    if text.count("]") > text.count("["):
        text = re.sub(r"\s*[^.\[\]]{0,60}\]\s*$", "", text)
    if GUTENBERG.search(text):
        text = " ".join(s for s in re.split(r"(?<=[.!?])\s+", text) if not GUTENBERG.search(s))
    text = ADDR_HEAD.sub("", text)
    text = BARE_MARKER.sub("", text)
    text = ITALIC.sub(r"\1", text)
    return re.sub(r"\s{2,}", " ", text).strip(), removed


def main():
    for name in ("Beethoven", "Mozart"):
        src = json.load(open(f"{SRC}/{name}_letters_parsed.json", encoding="utf-8"))
        out, removed = {}, {}
        n_in = n_out = 0
        for k, v in src.items():
            units = v if isinstance(v, list) else [str(v)]
            n_in += sum(len(u) for u in units)
            kept, cut = strip_letter(units)
            n_out += len(kept)
            if kept:
                out[k] = [kept]
            if cut:
                removed[k] = cut
        json.dump(out, open(f"{OUT}/{name}_letters_stripped.json", "w", encoding="utf-8"),
                  ensure_ascii=False)
        json.dump(removed, open(f"{OUT}/{name}_removed.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("%-10s  %d chars in, %d kept (-%.1f%%), %d letters"
              % (name, n_in, n_out, (n_in - n_out) / n_in * 100, len(out)))


if __name__ == "__main__":
    main()
