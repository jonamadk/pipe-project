// Ported from the original app/template.html renderer: turns the model's
// lightly-formatted answer text (**bold**, ⚠️ markers, "- " / "1. " lists)
// into the small HTML subset the assistant bubble understands.
export function renderAnswer(text) {
  let safe = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  safe = safe.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  safe = safe.replace(/⚠️/g, '<span class="caution">⚠️</span>');

  const lines = safe.split(/\n+/);
  let html = '';
  let inList = false;
  for (const line of lines) {
    const trimmed = line.trim();
    if (/^-\s+/.test(trimmed) || /^\d+\.\s+/.test(trimmed)) {
      if (!inList) {
        html += '<ul>';
        inList = true;
      }
      html += `<li>${trimmed.replace(/^-\s+/, '').replace(/^\d+\.\s+/, '')}</li>`;
    } else {
      if (inList) {
        html += '</ul>';
        inList = false;
      }
      if (trimmed) html += `<p>${trimmed}</p>`;
    }
  }
  if (inList) html += '</ul>';
  return html;
}
