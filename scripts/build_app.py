"""
Full build pipeline for the PIPE RAG prototype.

    data/raw/*.txt  --[chunk_documents.py]-->  data/chunks.json  --\
                                                                     +--> dist/index.html
    (hand-curated)  --[build_knowledge_graph.py]--> data/kg.json  --/

Usage:
  python scripts/build_app.py

Then open dist/index.html directly in a browser, or serve the
project's dist/ folder statically. No build tooling or server is
required for the prototype itself; the only network call it makes
at runtime is the generation call to the Anthropic API (see README
for how to swap that for a local model).
"""
import json, os, subprocess, sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
DATA_DIR = os.path.join(BASE_DIR, "data")
APP_DIR = os.path.join(BASE_DIR, "app")
DIST_DIR = os.path.join(BASE_DIR, "dist")


def run(script_name):
    path = os.path.join(SCRIPTS_DIR, script_name)
    print(f"--- running {script_name} ---")
    subprocess.run([sys.executable, path], check=True)


def main():
    os.makedirs(DIST_DIR, exist_ok=True)

    run("chunk_documents.py")
    run("build_knowledge_graph.py")
    run("build_alt_retrieval_data.py")

    with open(os.path.join(APP_DIR, "template.html")) as f:
        template = f.read()
    with open(os.path.join(DATA_DIR, "chunks.json")) as f:
        chunks_json = f.read()
    with open(os.path.join(DATA_DIR, "kg.json")) as f:
        kg_json = f.read()
    with open(os.path.join(DATA_DIR, "structured_facts.json")) as f:
        structured_json = f.read()
    with open(os.path.join(DATA_DIR, "compressed_summary.json")) as f:
        compressed_json = f.read()

    out = (template
           .replace("__CHUNKS_JSON__", chunks_json)
           .replace("__KG_JSON__", kg_json)
           .replace("__STRUCTURED_JSON__", structured_json)
           .replace("__COMPRESSED_JSON__", compressed_json))
    for placeholder in ["__CHUNKS_JSON__", "__KG_JSON__", "__STRUCTURED_JSON__", "__COMPRESSED_JSON__"]:
        if placeholder in out:
            raise RuntimeError(f"Template placeholder {placeholder} was not substituted.")

    out_path = os.path.join(DIST_DIR, "index.html")
    with open(out_path, "w") as f:
        f.write(out)

    print(f"\nBuilt {out_path} ({len(out):,} bytes)")


if __name__ == "__main__":
    main()
