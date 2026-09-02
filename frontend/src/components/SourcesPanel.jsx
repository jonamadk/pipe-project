function ChunkList({ chunks, docs }) {
  return chunks.map((c) => (
    <div className="source-item" key={c.id}>
      <div className="src-meta">
        {docs[c.doc]?.title ?? c.doc} — p.{c.page}
      </div>
      {c.text.slice(0, 220)}
      {c.text.length > 220 ? '…' : ''}
    </div>
  ));
}

export default function SourcesPanel({ mode, retrieval, docs }) {
  const chunks = retrieval.chunks || [];

  if (mode === 'assessment') {
    const profile = retrieval.profile || [];
    const structuredEntries = retrieval.structuredEntries || [];
    return (
      <div className="sources">
        <details>
          <summary>Building profile used ({profile.length} answers)</summary>
          {profile.map((a) => (
            <div className="source-item" key={a.id}>
              <div className="src-meta">{a.question}</div>
              {a.answer}
            </div>
          ))}
        </details>
        {structuredEntries.length > 0 && (
          <details>
            <summary>Exact parameter records referenced ({structuredEntries.length})</summary>
            {structuredEntries.map((e, i) => (
              <div key={i}>
                <div className="src-meta" style={{ marginTop: 8 }}>
                  {e.label}
                </div>
                {e.records.map((r, j) => (
                  <div className="source-item" key={j}>
                    [{r.kind}] {r.source}: {r.value}
                  </div>
                ))}
              </div>
            ))}
          </details>
        )}
        <details>
          <summary>
            {chunks.length} additional guidance passage{chunks.length !== 1 ? 's' : ''} retrieved
          </summary>
          <ChunkList chunks={chunks} docs={docs} />
        </details>
      </div>
    );
  }

  if (mode === 'graph') {
    const edges = retrieval.edges || [];
    if (!edges.length) {
      return (
        <div className="sources">
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>
            No entities in the knowledge graph matched this question — try mentioning a specific
            parameter, pathogen, material, or guidance body, or switch modes.
          </span>
        </div>
      );
    }
    return (
      <div className="sources">
        <details>
          <summary>
            Graph traversal: {edges.length} relations, {chunks.length} cited passage
            {chunks.length !== 1 ? 's' : ''}
          </summary>
          <div className="graph-path">
            {edges.map((e, i) => (
              <span className="triple" key={i}>
                {e.fromLabel} <span className="rel">—{e.relation}→</span> {e.toLabel}{' '}
                <em>({e.note})</em>
              </span>
            ))}
          </div>
          <ChunkList chunks={chunks} docs={docs} />
        </details>
      </div>
    );
  }

  if (mode === 'long_context') {
    return (
      <div className="sources">
        <details>
          <summary>Entire corpus handed over: {chunks.length} passages, no filtering</summary>
          <ChunkList chunks={chunks} docs={docs} />
        </details>
      </div>
    );
  }

  if (mode === 'compressed') {
    const digestEntries = retrieval.digestEntries || [];
    if (!digestEntries.length) {
      return (
        <div className="sources">
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>
            No digest entry matched this question.
          </span>
        </div>
      );
    }
    return (
      <div className="sources">
        <details>
          <summary>
            {digestEntries.length} digest entr{digestEntries.length > 1 ? 'ies' : 'y'} matched,
            citing {chunks.length} original passage{chunks.length !== 1 ? 's' : ''}
          </summary>
          {digestEntries.map((e) => (
            <div className="source-item" key={e.id}>
              <div className="src-meta">Digest: {e.title}</div>
              {e.text}
            </div>
          ))}
          <ChunkList chunks={chunks} docs={docs} />
        </details>
      </div>
    );
  }

  if (mode === 'structured') {
    if (retrieval.routedTo && retrieval.routedTo.startsWith('structured:')) {
      const chunksById = Object.fromEntries(chunks.map((c) => [c.id, c]));
      return (
        <div className="sources">
          <details open>
            <summary>
              Routed to exact table: {retrieval.entry.label} ({retrieval.records.length} records)
            </summary>
            {retrieval.records.map((r, i) => {
              const c = chunksById[r.chunk];
              return (
                <div className="source-item" key={i}>
                  <div className="src-meta">
                    [{r.kind}] {r.source} — {c ? `${docs[c.doc]?.title ?? c.doc}, p.${c.page}` : ''}
                  </div>
                  {r.value}
                </div>
              );
            })}
          </details>
        </div>
      );
    }
    return (
      <div className="sources">
        <details>
          <summary>No parameter matched — fell back to TF-IDF ({chunks.length} passages)</summary>
          <ChunkList chunks={chunks} docs={docs} />
        </details>
      </div>
    );
  }

  // vector (default) mode
  if (chunks.length) {
    return (
      <div className="sources">
        <details>
          <summary>
            {chunks.length} source passage{chunks.length > 1 ? 's' : ''} used
          </summary>
          <ChunkList chunks={chunks} docs={docs} />
        </details>
      </div>
    );
  }

  return (
    <div className="sources">
      <span style={{ fontSize: 12, color: 'var(--muted)' }}>
        No sufficiently relevant passage was found in the ingested documents.
      </span>
    </div>
  );
}
