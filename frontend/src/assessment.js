// A question is visible unless it declares a dependsOn condition that
// isn't currently satisfied by the given answers (e.g. a follow-up
// question that only appears once its parent question is answered "Yes").
export function isQuestionVisible(question, answers) {
  if (!question.dependsOn) return true;
  return answers[question.dependsOn.id] === question.dependsOn.value;
}

export function getVisibleQuestions(questions, answers) {
  return questions.filter((q) => isQuestionVisible(q, answers));
}
