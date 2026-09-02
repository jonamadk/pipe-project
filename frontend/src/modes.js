export const MODES = [
  { id: 'vector', label: 'TF-IDF', sub: 'vector search' },
  { id: 'graph', label: 'GraphRAG', sub: 'knowledge graph' },
  { id: 'long_context', label: 'Long-context', sub: 'whole corpus, no retrieval' },
  { id: 'compressed', label: 'Compressed', sub: 'summarize, then search' },
  { id: 'structured', label: 'Structured', sub: 'route to exact table' },
];

export const MODE_LABELS = {
  ...Object.fromEntries(MODES.map((m) => [m.id, m.label])),
  assessment: 'Building Assessment',
};
