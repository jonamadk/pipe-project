import { useEffect, useRef } from 'react';
import Message from './Message.jsx';

export default function Thread({ messages, thinking, docs, sampleQuestions, onSampleClick }) {
  const threadRef = useRef(null);

  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
    }
  }, [messages, thinking]);

  return (
    <div className="thread" ref={threadRef}>
      {messages.length === 0 && (
        <div className="empty-state">
          <h3>Two guidance papers are loaded</h3>
          <p>
            Try a question, or pick one below. Every answer will point back to the specific
            document and page it came from.
          </p>
          <div className="chips">
            {sampleQuestions.map((q) => (
              <div className="chip" key={q} onClick={() => onSampleClick(q)}>
                {q}
              </div>
            ))}
          </div>
        </div>
      )}
      {messages.map((m, i) => (
        <Message
          key={i}
          role={m.role}
          text={m.text}
          retrieval={m.retrieval}
          mode={m.mode}
          docs={docs}
        />
      ))}
      {thinking && (
        <div className="thinking">Retrieving relevant passages and drafting a grounded answer…</div>
      )}
    </div>
  );
}
