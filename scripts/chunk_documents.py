"""
Step 1 of the build pipeline: turn raw extracted-text guidance documents
into retrieval-ready passages ("chunks") with document + page metadata.

The document list (DOCS) is read from data/raw/manifest.json rather than
hardcoded here, so new documents can be registered without editing this
file. The source of truth for those documents is a Google Drive folder;
see the "sync-pipe-drive" skill for the procedure to pull in new or
changed files from there, normalize them into data/raw/*.txt, and add
their manifest entry.

Add a new guidance document by hand (without the Drive skill):
  1. Dropping a cleaned .txt file into data/raw/, with [Page N] or
     [Page N-M] markers wherever a new page starts (see existing files
     for the expected format).
  2. Adding an entry to data/raw/manifest.json's "documents" list.
  3. Re-running the full build: python scripts/build_app.py

Usage:
  python scripts/chunk_documents.py
Reads from:  data/raw/manifest.json, data/raw/*.txt
Writes to:   data/chunks.json
"""
import re, json, os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
OUT_PATH = os.path.join(BASE_DIR, "data", "chunks.json")
MANIFEST_PATH = os.path.join(RAW_DIR, "manifest.json")

with open(MANIFEST_PATH) as f:
    _manifest = json.load(f)

DOCS = [
    {
        "id": d["id"],
        "title": d["title"],
        "short": d["short"],
        "path": os.path.join(RAW_DIR, d["file"]),
    }
    for d in _manifest["documents"]
]

MAX_WORDS = 180

def split_into_word_chunks(text, max_words=MAX_WORDS):
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = []
    current_words = 0
    for p in paras:
        w = len(p.split())
        if current_words + w > max_words and current:
            chunks.append(" ".join(current))
            current = []
            current_words = 0
        current.append(p)
        current_words += w
    if current:
        chunks.append(" ".join(current))
    return chunks

all_chunks = []
cid = 0
for doc in DOCS:
    with open(doc["path"], "r") as f:
        raw = f.read()
    # Split on [Page N] or [Page N-M] markers
    parts = re.split(r"\[Page ([\d\-]+)\]", raw)
    # parts[0] is preamble before first page marker (title etc.) -> treat as page "1"
    preamble = parts[0].strip()
    page_text_pairs = []
    if preamble:
        page_text_pairs.append(("1", preamble))
    for i in range(1, len(parts), 2):
        page_label = parts[i]
        text = parts[i+1].strip() if i+1 < len(parts) else ""
        if text:
            page_text_pairs.append((page_label, text))

    for page_label, text in page_text_pairs:
        for sub in split_into_word_chunks(text):
            cid += 1
            all_chunks.append({
                "id": f"c{cid}",
                "doc": doc["id"],
                "title": doc["title"],
                "short": doc["short"],
                "page": page_label,
                "text": sub,
            })

print(f"Total chunks: {len(all_chunks)}")
with open(OUT_PATH, "w") as f:
    json.dump(all_chunks, f, separators=(",", ":"))
print(f"Wrote {OUT_PATH}")

# quick sanity print
for c in all_chunks[:3]:
    print(c["doc"], c["page"], c["text"][:80])
