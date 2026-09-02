import { useState } from 'react';
import { MODES } from '../modes.js';

export default function Sidebar({ docs, mode, setMode, onOpenAssessment }) {
  const [howOpen, setHowOpen] = useState(false);

  return (
    <div className="sidebar">
      <div className="kicker">Prototype</div>
      <h1>PIPE</h1>
      <p className="sub">
        Plumbing Information &amp; Performance Evaluation — a retrieval-grounded Q&amp;A demo.
        Answers come only from the two ingested guidance papers below, not from general model
        knowledge.
      </p>

      <div id="doc-list">
        {Object.entries(docs).map(([id, d]) => (
          <div className="doc-card" key={id}>
            <div className="t">{d.title}</div>
            <div className="m">{d.meta}</div>
          </div>
        ))}
      </div>

      <button className="assessment-launch" type="button" onClick={onOpenAssessment}>
        Basic PIPE Assessment Form
        <span>18-question building intake · generates a cited risk report</span>
      </button>

      <div className="mode-picker">
        <div className="mode-label">Retrieval method</div>
        <div className="mode-toggle">
          {MODES.map((m) => (
            <button
              key={m.id}
              className={`mode-btn${mode === m.id ? ' active' : ''}`}
              onClick={() => setMode(m.id)}
              type="button"
            >
              {m.label}
              <span>{m.sub}</span>
            </button>
          ))}
        </div>
      </div>

      <button className="how-toggle" type="button" onClick={() => setHowOpen((v) => !v)}>
        How this demo works
      </button>
      <div className={`how-box${howOpen ? ' open' : ''}`}>
        Five retrieval strategies, all running server-side in the Python backend — pick one above:
        <br />
        <br />
        <strong>TF-IDF vector search</strong> — bag-of-words similarity scoring across all 39
        passages. The standard RAG baseline.
        <br />
        <br />
        <strong>GraphRAG</strong> — a small hand-built knowledge graph (25 entities, 29 relations)
        is traversed from any entities named in your question, surfacing multi-hop connections
        text search would miss.
        <br />
        <br />
        <strong>Long-context</strong> — no retrieval step at all. The entire corpus (all 39
        passages, ~5,000 words) is handed to the model every time. Simple and always complete, but
        the most expensive per question by far.
        <br />
        <br />
        <strong>Compressed (memory compression)</strong> — searches a pre-written 10-entry digest
        of the corpus instead of the raw passages, then cites back to the original chunks it
        summarizes. Much smaller search space, at some cost to recall.
        <br />
        <br />
        <strong>Structured (routed retrieval)</strong> — your question is checked against a table
        of 9 known parameters (temperatures, residual levels, flushing frequency, etc.). If it
        names one, you get the exact guidance + survey records for that parameter with no fuzzy
        matching at all. Otherwise it falls back to TF-IDF.
        <br />
        <br />
        Every mode hands its result to the selected model (Anthropic or OpenAI) under the same
        strict system prompt: answer only from what was retrieved, cite document + page, and say
        so explicitly if it doesn't cover the question. In a production PIPE deployment the
        generation step would run on a local, on-premise LLM instead of a cloud API — this
        prototype substitutes a hosted model to demonstrate the full pipeline end-to-end.
      </div>
    </div>
  );
}
