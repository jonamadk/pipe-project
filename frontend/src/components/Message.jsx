import { renderAnswer } from '../utils/renderAnswer.js';
import { MODE_LABELS } from '../modes.js';
import SourcesPanel from './SourcesPanel.jsx';

export default function Message({ role, text, retrieval, mode, docs }) {
  if (role === 'user') {
    return (
      <div className="msg user">
        <div className="bubble-label">You</div>
        <div className="bubble">{text}</div>
      </div>
    );
  }

  return (
    <div className="msg assistant">
      <div className="bubble-label">PIPE · {MODE_LABELS[mode] || mode}</div>
      <div className="bubble">
        <div dangerouslySetInnerHTML={{ __html: renderAnswer(text) }} />
        {retrieval && <SourcesPanel mode={mode} retrieval={retrieval} docs={docs} />}
      </div>
    </div>
  );
}
