import { getVisibleQuestions, isQuestionVisible } from '../assessment.js';

export default function AssessmentForm({ questions, answers, setAnswer, onSubmit, onClose, submitting }) {
  const sections = [];
  for (const q of questions) {
    if (!sections.includes(q.section)) sections.push(q.section);
  }
  const visibleQuestions = getVisibleQuestions(questions, answers);
  const answeredCount = visibleQuestions.filter((q) => answers[q.id]).length;
  const allAnswered = visibleQuestions.length > 0 && answeredCount === visibleQuestions.length;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <div className="kicker">Decision Support Tool</div>
            <h2>Basic PIPE Assessment Form</h2>
            <p className="sub">
              Answer these questions to help assess whether a water quality management plan is
              required for your building, and identify plumbing features that warrant special
              guidance.
            </p>
          </div>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <div className="modal-body">
          {sections.map((section) => (
            <div className="assessment-section" key={section}>
              <h3>{section}</h3>
              {questions
                .filter((q) => q.section === section && isQuestionVisible(q, answers))
                .map((q) => (
                  <div className={`assessment-q${q.dependsOn ? ' assessment-q--followup' : ''}`} key={q.id}>
                    <div className="assessment-q-text">
                      {q.id.replace('q', '')}. {q.text}
                    </div>
                    <div className="assessment-options">
                      {q.options.map((opt) => (
                        <label className="assessment-option" key={opt}>
                          <input
                            type="radio"
                            name={q.id}
                            value={opt}
                            checked={answers[q.id] === opt}
                            onChange={() => setAnswer(q.id, opt)}
                          />
                          {opt}
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
            </div>
          ))}
        </div>

        <div className="modal-footer">
          <span className="assessment-progress">
            {answeredCount} / {visibleQuestions.length} answered
          </span>
          <button type="button" onClick={onSubmit} disabled={!allAnswered || submitting}>
            {submitting ? 'Assessing…' : 'Submit Assessment'}
          </button>
        </div>
      </div>
    </div>
  );
}
