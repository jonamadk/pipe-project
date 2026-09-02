export default function TopBar({ provider, setProvider, apiKey, setApiKey }) {
  return (
    <div className="topbar">
      <div className="eyebrow">Retrieval-grounded · Source-cited</div>
      <h2>Ask about plumbing water quality &amp; Legionella risk</h2>
      <div className="apikey-row">
        <select value={provider} onChange={(e) => setProvider(e.target.value)}>
          <option value="anthropic">Anthropic</option>
          <option value="openai">OpenAI</option>
        </select>
        <input
          id="api-key-input"
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={provider === 'anthropic' ? 'sk-ant-...' : 'sk-...'}
          autoComplete="off"
        />
        <span className="apikey-status">
          stored only in this browser, sent only to your local backend
        </span>
      </div>
    </div>
  );
}
