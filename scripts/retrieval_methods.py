"""
Five retrieval strategies over the same PIPE guidance-document corpus,
implemented in plain Python (no external dependencies) so evaluate.py
can score them side by side without needing a browser.

    1. vector_retrieve       - TF-IDF cosine similarity over all chunks (baseline RAG)
    2. graph_retrieve        - entity match + knowledge-graph traversal (GraphRAG)
    3. long_context_retrieve - no retrieval at all; hand the whole corpus to the model
    4. compressed_retrieve   - keyword match against a pre-summarized digest, not raw chunks
    5. structured_retrieve   - classify the question, route to an exact table lookup;
                               fall back to vector_retrieve if nothing routes

Each function returns a dict: {"chunk_ids": [...], "context": "<text handed to the LLM>", "meta": {...}}
"chunk_ids" is what evaluate.py scores against each question's gold chunk ids.
"""
import json, math, os, re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

STOP = set("""a an the of to in in in on for and or is are was were be been being this that these those with
as at by from it its their they them he she his her we our you your not no can may might should would could
shall will do does did have has had if than then so such more most less least also into about across per
within without between during over under above below up down out i.e e.g""".split())


def load_corpus():
    with open(os.path.join(DATA_DIR, "chunks.json")) as f:
        chunks = json.load(f)
    with open(os.path.join(DATA_DIR, "kg.json")) as f:
        kg = json.load(f)
    with open(os.path.join(DATA_DIR, "structured_facts.json")) as f:
        structured = json.load(f)
    with open(os.path.join(DATA_DIR, "compressed_summary.json")) as f:
        compressed = json.load(f)
    chunks_by_id = {c["id"]: c for c in chunks}
    return chunks, chunks_by_id, kg, structured, compressed


def tokenize(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9%°><=\-.\s]", " ", text)
    return [t for t in text.split() if len(t) > 1 and t not in STOP]


# ---------------------------------------------------------------------------
# 1. TF-IDF vector search (baseline RAG)
# ---------------------------------------------------------------------------
class TfidfIndex:
    def __init__(self, chunks):
        self.chunks = chunks
        self.tokens = [tokenize(c["text"]) for c in chunks]
        n = len(chunks)
        df = {}
        for toks in self.tokens:
            for t in set(toks):
                df[t] = df.get(t, 0) + 1
        self.idf = {t: math.log((n + 1) / (df[t] + 1)) + 1 for t in df}
        self.vectors = [self._vectorize(toks) for toks in self.tokens]

    def _vectorize(self, tokens):
        tf = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        vec = {}
        norm = 0.0
        for t, c in tf.items():
            w = c * self.idf.get(t, math.log(len(self.chunks) + 1) + 1)
            vec[t] = w
            norm += w * w
        norm = math.sqrt(norm) or 1.0
        return {t: w / norm for t, w in vec.items()}

    @staticmethod
    def _cosine(a, b):
        keys = a.keys() if len(a) < len(b) else b.keys()
        return sum(a[k] * b[k] for k in keys if k in a and k in b)

    def search(self, query, k=5, min_score=0.02):
        qvec = self._vectorize(tokenize(query))
        scored = [(self._cosine(qvec, v), c) for v, c in zip(self.vectors, self.chunks)]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [(s, c) for s, c in scored[:k] if s > min_score]


def vector_retrieve(query, chunks, index=None, k=5):
    index = index or TfidfIndex(chunks)
    results = index.search(query, k=k)
    chunk_ids = [c["id"] for _, c in results]
    context = "\n\n".join(f"[{c['doc']} p.{c['page']}] {c['text']}" for _, c in results)
    return {"chunk_ids": chunk_ids, "context": context, "meta": {"scores": [round(s, 3) for s, _ in results]}}


# ---------------------------------------------------------------------------
# 2. GraphRAG: entity match + graph traversal
# ---------------------------------------------------------------------------
def match_entities(query, kg):
    q = query.lower()
    return [nid for nid, node in kg["nodes"].items() if any(a in q for a in node["aliases"])]


def graph_retrieve(query, kg, chunks_by_id, max_hops=2, max_edges=10):
    seeds = match_entities(query, kg)
    if not seeds:
        return {"chunk_ids": [], "context": "", "meta": {"seeds": [], "edges": []}}
    frontier = set(seeds)
    visited_keys = set()
    visited_edges = []
    for _ in range(max_hops):
        if len(visited_edges) >= max_edges:
            break
        next_frontier = set()
        for e in kg["edges"]:
            key = (e["from"], e["relation"], e["to"])
            if key in visited_keys:
                continue
            if e["from"] in frontier or e["to"] in frontier:
                visited_edges.append(e)
                visited_keys.add(key)
                next_frontier.add(e["from"])
                next_frontier.add(e["to"])
        frontier = next_frontier
        if len(visited_edges) >= max_edges:
            break
    visited_edges = visited_edges[:max_edges]
    chunk_ids = sorted({cid for e in visited_edges for cid in e["chunks"]})
    triples = [
        f"{kg['nodes'][e['from']]['label']} --{e['relation']}--> {kg['nodes'][e['to']]['label']} ({e['note']})"
        for e in visited_edges
    ]
    excerpts = "\n\n".join(f"[{chunks_by_id[cid]['doc']} p.{chunks_by_id[cid]['page']}] {chunks_by_id[cid]['text']}" for cid in chunk_ids if cid in chunks_by_id)
    context = "GRAPH RELATIONS:\n" + "\n".join(triples) + "\n\nSUPPORTING EXCERPTS:\n" + excerpts
    return {"chunk_ids": chunk_ids, "context": context, "meta": {"seeds": seeds, "edges": len(visited_edges), "edge_list": visited_edges}}


# ---------------------------------------------------------------------------
# 3. Long-context prompting: no retrieval, hand over everything
# ---------------------------------------------------------------------------
def long_context_retrieve(query, chunks):
    chunk_ids = [c["id"] for c in chunks]
    context = "\n\n".join(f"[{c['doc']} p.{c['page']}] {c['text']}" for c in chunks)
    return {"chunk_ids": chunk_ids, "context": context, "meta": {"note": "entire corpus, no filtering"}}


# ---------------------------------------------------------------------------
# 4. Memory compression: retrieve against a pre-summarized digest
# ---------------------------------------------------------------------------
def compressed_retrieve(query, compressed, k=3):
    q_tokens = set(tokenize(query))
    scored = []
    for entry in compressed:
        entry_tokens = set(tokenize(entry["title"] + " " + entry["text"]))
        overlap = len(q_tokens & entry_tokens)
        if overlap:
            scored.append((overlap, entry))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [e for _, e in scored[:k]]
    chunk_ids = sorted({cid for e in top for cid in e["source_chunks"]})
    context = "\n\n".join(f"[{e['title']}] {e['text']}" for e in top)
    return {"chunk_ids": chunk_ids, "context": context, "meta": {"digest_entries_matched": [e["id"] for e in top]}}


# ---------------------------------------------------------------------------
# 5. Structured retrieval: classify -> exact lookup, else fall back to vector
# ---------------------------------------------------------------------------
def classify_parameter(query, structured):
    q = query.lower()
    for key, entry in structured.items():
        if any(alias in q for alias in entry["aliases"]):
            return key
    return None


def structured_retrieve(query, structured, chunks_by_id, index, k_fallback=5):
    param = classify_parameter(query, structured)
    if param is None:
        result = vector_retrieve(query, list(chunks_by_id.values()), index=index, k=k_fallback)
        result["meta"]["routed_to"] = "vector_fallback"
        return result
    entry = structured[param]
    chunk_ids = sorted({r["chunk"] for r in entry["records"]})
    lines = [f"- [{r['kind']}] {r['source']}: {r['value']}" for r in entry["records"]]
    context = f"PARAMETER: {entry['label']}\n" + "\n".join(lines)
    return {"chunk_ids": chunk_ids, "context": context, "meta": {"routed_to": f"structured:{param}"}}


METHODS = ["vector", "graph", "long_context", "compressed", "structured"]


def run_method(method, query, chunks, chunks_by_id, kg, structured, compressed, tfidf_index):
    if method == "vector":
        return vector_retrieve(query, chunks, index=tfidf_index)
    if method == "graph":
        return graph_retrieve(query, kg, chunks_by_id)
    if method == "long_context":
        return long_context_retrieve(query, chunks)
    if method == "compressed":
        return compressed_retrieve(query, compressed)
    if method == "structured":
        return structured_retrieve(query, structured, chunks_by_id, tfidf_index)
    raise ValueError(f"unknown method: {method}")
