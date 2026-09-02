const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function fetchMeta() {
  const res = await fetch(`${API_BASE}/api/meta`);
  if (!res.ok) throw new Error('Failed to load app metadata from the backend.');
  return res.json();
}

export async function submitAssessment({ provider, apiKey, answers }) {
  const res = await fetch(`${API_BASE}/api/assess`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      provider,
      api_key: apiKey,
      answers,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Something went wrong generating the assessment.');
  }
  return data; // { answer, mode, retrieval }
}

export async function askQuestion({ question, mode, provider, apiKey, history }) {
  const res = await fetch(`${API_BASE}/api/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      mode,
      provider,
      api_key: apiKey,
      history,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Something went wrong reaching the model.');
  }
  return data; // { answer, mode, retrieval }
}
