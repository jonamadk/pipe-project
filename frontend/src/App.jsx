import { useEffect, useState } from 'react';
import Sidebar from './components/Sidebar.jsx';
import TopBar from './components/TopBar.jsx';
import Thread from './components/Thread.jsx';
import Composer from './components/Composer.jsx';
import AssessmentForm from './components/AssessmentForm.jsx';
import { fetchMeta, askQuestion, submitAssessment } from './api.js';
import { getVisibleQuestions } from './assessment.js';

export default function App() {
  const [docs, setDocs] = useState({});
  const [sampleQuestions, setSampleQuestions] = useState([]);
  const [assessmentQuestions, setAssessmentQuestions] = useState([]);
  const [metaError, setMetaError] = useState(null);

  const [assessmentOpen, setAssessmentOpen] = useState(false);
  const [assessmentAnswers, setAssessmentAnswers] = useState({});
  const [assessmentSubmitting, setAssessmentSubmitting] = useState(false);

  const [mode, setMode] = useState('vector');
  const [provider, setProviderState] = useState(
    () => localStorage.getItem('pipe_provider') || 'anthropic'
  );
  const [anthropicKey, setAnthropicKey] = useState(
    () => localStorage.getItem('pipe_anthropic_key') || ''
  );
  const [openaiKey, setOpenaiKey] = useState(
    () => localStorage.getItem('pipe_openai_key') || ''
  );

  const [inputValue, setInputValue] = useState('');
  const [messages, setMessages] = useState([]);
  const [history, setHistory] = useState([]);
  const [thinking, setThinking] = useState(false);

  useEffect(() => {
    fetchMeta()
      .then((data) => {
        setDocs(data.docs);
        setSampleQuestions(data.sample_questions);
        setAssessmentQuestions(data.assessment_questions);
      })
      .catch((err) => setMetaError(err.message));
  }, []);

  function setProvider(p) {
    setProviderState(p);
    localStorage.setItem('pipe_provider', p);
  }

  function setApiKey(value) {
    if (provider === 'anthropic') {
      setAnthropicKey(value);
      localStorage.setItem('pipe_anthropic_key', value);
    } else {
      setOpenaiKey(value);
      localStorage.setItem('pipe_openai_key', value);
    }
  }

  const apiKey = provider === 'anthropic' ? anthropicKey : openaiKey;

  async function handleSubmit(question) {
    const q = (question ?? inputValue).trim();
    if (!q || thinking) return;

    setMessages((prev) => [...prev, { role: 'user', text: q }]);
    setInputValue('');
    setThinking(true);

    if (!apiKey.trim()) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `Something went wrong reaching the model: enter your ${
            provider === 'anthropic' ? 'Anthropic' : 'OpenAI'
          } API key above first`,
          retrieval: { chunks: [] },
          mode,
        },
      ]);
      setThinking(false);
      return;
    }

    try {
      const { answer, retrieval, mode: modeUsed } = await askQuestion({
        question: q,
        mode,
        provider,
        apiKey,
        history,
      });
      setMessages((prev) => [...prev, { role: 'assistant', text: answer, retrieval, mode: modeUsed }]);
      setHistory((prev) => {
        const next = [...prev, { role: 'user', content: q }, { role: 'assistant', content: answer }];
        return next.slice(-8);
      });
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `Something went wrong reaching the model: ${err.message}`,
          retrieval: { chunks: [] },
          mode,
        },
      ]);
    } finally {
      setThinking(false);
    }
  }

  function setAssessmentAnswer(qid, value) {
    setAssessmentAnswers((prev) => {
      const next = { ...prev, [qid]: value };
      // Clear any follow-up question's answer if it's no longer triggered
      // by this change (e.g. switching q5 away from "Chlorine" drops q5a).
      for (const q of assessmentQuestions) {
        if (q.dependsOn && q.dependsOn.id === qid && q.dependsOn.value !== value) {
          delete next[q.id];
        }
      }
      return next;
    });
  }

  async function handleAssessmentSubmit() {
    const answers = getVisibleQuestions(assessmentQuestions, assessmentAnswers).map((q) => ({
      id: q.id,
      question: q.text,
      answer: assessmentAnswers[q.id],
    }));

    if (!apiKey.trim()) {
      setAssessmentOpen(false);
      setMessages((prev) => [
        ...prev,
        { role: 'user', text: `Submitted building assessment (${answers.length}/${answers.length} answered)` },
        {
          role: 'assistant',
          text: `Something went wrong reaching the model: enter your ${
            provider === 'anthropic' ? 'Anthropic' : 'OpenAI'
          } API key above first`,
          retrieval: { chunks: [] },
          mode: 'assessment',
        },
      ]);
      return;
    }

    setAssessmentSubmitting(true);
    try {
      const { answer, retrieval, mode: modeUsed } = await submitAssessment({
        provider,
        apiKey,
        answers,
      });
      setAssessmentOpen(false);
      setMessages((prev) => [
        ...prev,
        { role: 'user', text: `Submitted building assessment (${answers.length}/${answers.length} answered)` },
        { role: 'assistant', text: answer, retrieval, mode: modeUsed },
      ]);
    } catch (err) {
      setAssessmentOpen(false);
      setMessages((prev) => [
        ...prev,
        { role: 'user', text: `Submitted building assessment (${answers.length}/${answers.length} answered)` },
        {
          role: 'assistant',
          text: `Something went wrong reaching the model: ${err.message}`,
          retrieval: { chunks: [] },
          mode: 'assessment',
        },
      ]);
    } finally {
      setAssessmentSubmitting(false);
    }
  }

  return (
    <div className="app">
      <Sidebar docs={docs} mode={mode} setMode={setMode} onOpenAssessment={() => setAssessmentOpen(true)} />
      {assessmentOpen && (
        <AssessmentForm
          questions={assessmentQuestions}
          answers={assessmentAnswers}
          setAnswer={setAssessmentAnswer}
          onSubmit={handleAssessmentSubmit}
          onClose={() => setAssessmentOpen(false)}
          submitting={assessmentSubmitting}
        />
      )}
      <div className="main">
        <TopBar provider={provider} setProvider={setProvider} apiKey={apiKey} setApiKey={setApiKey} />
        {metaError ? (
          <div className="thread">
            <div className="empty-state">
              <h3>Couldn't reach the backend</h3>
              <p>{metaError} — is the FastAPI server running at the configured API base URL?</p>
            </div>
          </div>
        ) : (
          <Thread
            messages={messages}
            thinking={thinking}
            docs={docs}
            sampleQuestions={sampleQuestions}
            onSampleClick={(q) => handleSubmit(q)}
          />
        )}
        <Composer
          value={inputValue}
          onChange={setInputValue}
          onSubmit={() => handleSubmit()}
          disabled={thinking}
        />
      </div>
    </div>
  );
}
