"""
Extract letters from the TEI edition, with the editorial notes that accompany them.
Outputs:
  data/pilot_letters_v2.json   text, gold person annotations and notes context, per letter
"""

import zipfile, json, re
from lxml import etree
from pathlib import Path

TEI = "http://www.tei-c.org/ns/1.0"
VG  = "http://www.vangoghletters.org/ns/"

PILOT = [
    "let596","let602","let632","let655","let656",
    "let682","let683","let686","let694","let695",
    "let698","let699","let736","let776","let784",
]

def get_meta(root):
    def t(el): return el.text.strip() if el is not None and el.text else ""
    return {
        "date":  t(root.find(f".//{{{VG}}}dateLet")),
        "to":    t(root.find(f".//{{{VG}}}addressee")),
        "place": t(root.find(f".//{{{VG}}}placeLet")),
    }

def extract_div(body, div_type):
    """Extract clean text from a named div."""
    for div in body:
        if div.get("type") == div_type:
            paras = []
            for ab in div.iter(f"{{{TEI}}}ab"):
                text = re.sub(r"\s+", " ", "".join(ab.itertext()).strip())
                if text:
                    paras.append(text)
            return "\n\n".join(paras)
    return ""

def extract_pers_gold(body):
    """Extract gold person annotations from translation div."""
    gold = {}
    for div in body:
        if div.get("type") == "translation":
            for rs in div.findall(f".//{{{TEI}}}rs[@type='pers']"):
                key = rs.get("key", "")
                mention = "".join(rs.itertext()).strip()
                if mention:
                    if key not in gold:
                        gold[key] = {"key": key, "mentions": []}
                    if mention not in gold[key]["mentions"]:
                        gold[key]["mentions"].append(mention)
    return list(gold.values())

def extract_ill_gold(body):
    """Extract artwork F-number references from notes div."""
    ills = []
    for div in body:
        if div.get("type") == "notes":
            for rs in div.findall(f".//{{{TEI}}}rs[@type='ill']"):
                key = rs.get("key", "")
                text = "".join(rs.itertext()).strip()
                if text:
                    ills.append({"key": key, "f_number": text})
    return ills

def extract_notes_clean(body):
    """Extract editorial notes as plain text (oracle context)."""
    for div in body:
        if div.get("type") == "notes":
            paras = []
            for note in div.findall(f"{{{TEI}}}note"):
                text = re.sub(r"\s+", " ", "".join(note.itertext()).strip())
                if text and len(text) > 20:
                    paras.append(text)
            return "\n".join(paras[:15])  # top 15 notes, avoid token bloat
    return ""

def main():
    results = []
    with zipfile.ZipFile("data/vangoghxml.zip") as z:
        for lid in PILOT:
            root = etree.fromstring(z.read(f"{lid}.xml"))
            meta = get_meta(root)
            body = root.find(f".//{{{TEI}}}body")
            text         = extract_div(body, "translation")
            pers_gold    = extract_pers_gold(body)
            ill_gold     = extract_ill_gold(body)
            notes_text   = extract_notes_clean(body)
            words        = len(text.split())
            n_pers       = sum(len(p["mentions"]) for p in pers_gold)
            n_ills       = len(ill_gold)
            print(f"  {lid:<9} {words:>5}w  pers_gold={n_pers:>3}  ill_refs={n_ills:>3}")
            results.append({
                "id": lid, **meta,
                "words": words,
                "text": text,
                "pers_gold": pers_gold,
                "ill_gold": ill_gold,
                "notes_context": notes_text,
            })
    Path("data/pilot_letters_v2.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2)
    )
    total_pers = sum(sum(len(p["mentions"]) for p in r["pers_gold"]) for r in results)
    total_ills = sum(len(r["ill_gold"]) for r in results)
    print(f"\nTotal pers gold mentions: {total_pers}")
    print(f"Total ill (F-number) refs: {total_ills}")
    print(f"Wrote → data/pilot_letters_v2.json")

if __name__ == "__main__":
    main()
