import os
import sys
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "scripts"))
import retrieval_methods as rm  # noqa: E402

import prompts  # noqa: E402
import providers  # noqa: E402
from constants import (  # noqa: E402
    DOC_META,
    SAMPLE_QUESTIONS,
    ASSESSMENT_QUESTIONS,
    QUESTION_TO_STRUCTURED_PARAM,
)

app = FastAPI(title="PIPE API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CHUNKS, CHUNKS_BY_ID, KG, STRUCTURED, COMPRESSED = rm.load_corpus()
TFIDF_INDEX = rm.TfidfIndex(CHUNKS)


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AskRequest(BaseModel):
    question: str
    mode: Literal["vector", "graph", "long_context", "compressed", "structured"]
    provider: Literal["anthropic", "openai"]
    api_key: str
    history: list[HistoryMessage] = []


class AskResponse(BaseModel):
    answer: str
    mode: str
    retrieval: dict


class AssessmentAnswer(BaseModel):
    id: str
    question: str
    answer: str


class AssessRequest(BaseModel):
    provider: Literal["anthropic", "openai"]
    api_key: str
    answers: list[AssessmentAnswer]


class AssessResponse(BaseModel):
    answer: str
    mode: str
    retrieval: dict


def _chunks_for_ids(chunk_ids):
    return [CHUNKS_BY_ID[cid] for cid in chunk_ids if cid in CHUNKS_BY_ID]


def build_retrieval_and_prompt(mode, question):
    if mode == "graph":
        seeds = rm.match_entities(question, KG)
        if not seeds:
            system_prompt = prompts.system_prompt_template(
                "(no matching entities found in the knowledge graph for this question)"
            )
            return system_prompt, {"seeds": [], "edges": [], "chunks": []}
        result = rm.graph_retrieve(question, KG, CHUNKS_BY_ID)
        edges = result["meta"]["edge_list"]
        chunks = _chunks_for_ids(result["chunk_ids"])
        system_prompt = prompts.build_graph_prompt(edges, chunks, KG)
        edges_for_ui = [
            {**e, "fromLabel": KG["nodes"][e["from"]]["label"], "toLabel": KG["nodes"][e["to"]]["label"]}
            for e in edges
        ]
        return system_prompt, {"seeds": seeds, "edges": edges_for_ui, "chunks": chunks}

    if mode == "long_context":
        system_prompt = prompts.build_long_context_prompt(CHUNKS)
        return system_prompt, {"chunks": CHUNKS}

    if mode == "compressed":
        result = rm.compressed_retrieve(question, COMPRESSED)
        matched_ids = result["meta"]["digest_entries_matched"]
        digest_entries = [e for e in COMPRESSED if e["id"] in matched_ids]
        chunks = _chunks_for_ids(result["chunk_ids"])
        system_prompt = prompts.build_compressed_prompt(digest_entries, chunks)
        return system_prompt, {"digestEntries": digest_entries, "chunks": chunks}

    if mode == "structured":
        param = rm.classify_parameter(question, STRUCTURED)
        if param is None:
            result = rm.vector_retrieve(question, CHUNKS, index=TFIDF_INDEX)
            chunks = _chunks_for_ids(result["chunk_ids"])
            system_prompt = prompts.system_prompt_template(
                prompts.format_excerpts(chunks) or "(no relevant excerpts found)"
            )
            return system_prompt, {"routedTo": "vector_fallback", "chunks": chunks}
        entry = STRUCTURED[param]
        system_prompt = prompts.build_structured_prompt(entry, CHUNKS_BY_ID)
        records_chunks = _chunks_for_ids(list(dict.fromkeys(r["chunk"] for r in entry["records"])))
        return system_prompt, {
            "routedTo": f"structured:{param}",
            "param": param,
            "entry": entry,
            "records": entry["records"],
            "chunks": records_chunks,
        }

    # vector (default) mode
    result = rm.vector_retrieve(question, CHUNKS, index=TFIDF_INDEX)
    chunks = _chunks_for_ids(result["chunk_ids"])
    system_prompt = prompts.system_prompt_template(
        prompts.format_excerpts(chunks) or "(no relevant excerpts found)"
    )
    return system_prompt, {"chunks": chunks}


@app.get("/api/meta")
def get_meta():
    return {
        "docs": DOC_META,
        "sample_questions": SAMPLE_QUESTIONS,
        "assessment_questions": ASSESSMENT_QUESTIONS,
    }


@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest):
    if not req.api_key.strip():
        raise HTTPException(status_code=400, detail="API key is required.")

    system_prompt, retrieval_for_ui = build_retrieval_and_prompt(req.mode, req.question)
    messages = [m.model_dump() for m in req.history] + [{"role": "user", "content": req.question}]

    try:
        if req.provider == "anthropic":
            answer = providers.call_anthropic(req.api_key, system_prompt, messages)
        else:
            answer = providers.call_openai(req.api_key, system_prompt, messages)
    except providers.ProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return AskResponse(answer=answer, mode=req.mode, retrieval=retrieval_for_ui)


@app.post("/api/assess", response_model=AssessResponse)
def assess(req: AssessRequest):
    if not req.api_key.strip():
        raise HTTPException(status_code=400, detail="API key is required.")
    if not req.answers:
        raise HTTPException(status_code=400, detail="No assessment answers were submitted.")

    profile_lines = "\n".join(f"- {a.question} → {a.answer}" for a in req.answers)

    structured_entries = []
    for a in req.answers:
        param = QUESTION_TO_STRUCTURED_PARAM.get(a.id)
        if param and param in STRUCTURED:
            structured_entries.append(STRUCTURED[param])

    query_text = " ".join(f"{a.question} {a.answer}" for a in req.answers)
    result = rm.vector_retrieve(query_text, CHUNKS, index=TFIDF_INDEX, k=20)
    chunks = _chunks_for_ids(result["chunk_ids"])

    system_prompt = prompts.build_assessment_prompt(profile_lines, structured_entries, chunks, CHUNKS_BY_ID)
    messages = [{"role": "user", "content": "Generate the PIPE building risk assessment from the profile and guidance above."}]

    try:
        if req.provider == "anthropic":
            answer = providers.call_anthropic(req.api_key, system_prompt, messages, max_tokens=6000)
        else:
            answer = providers.call_openai(req.api_key, system_prompt, messages, max_tokens=6000)
    except providers.ProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))

    retrieval_for_ui = {
        "profile": [a.model_dump() for a in req.answers],
        "structuredEntries": structured_entries,
        "chunks": chunks,
    }
    return AssessResponse(answer=answer, mode="assessment", retrieval=retrieval_for_ui)
