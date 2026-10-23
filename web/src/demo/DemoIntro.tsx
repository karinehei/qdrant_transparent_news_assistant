import { DEMO_SCENARIOS, type ScenarioId } from './scenarios'

interface DemoIntroProps {
  loading: boolean
  disabled: boolean
  onRunScenario: (id: ScenarioId) => void
  onFillQuestion: (question: string) => void
}

export default function DemoIntro({
  loading,
  disabled,
  onRunScenario,
  onFillQuestion,
}: DemoIntroProps) {
  return (
    <section className="demo-intro" aria-labelledby="demo-intro-heading">
      <h2 id="demo-intro-heading">Prepared scenarios</h2>
      <p>
        This browser demo uses synthetic news-style content and illustrative retrieval scores.
        Safety and citation examples illustrate behavior; they do not execute the backend&apos;s
        safety checks. Free-text is limited to documented example questions.
      </p>
      <div className="scenario-buttons" role="group" aria-label="Demo scenarios">
        {DEMO_SCENARIOS.map((s) => (
          <button
            key={s.id}
            type="button"
            className="scenario-button"
            onClick={() => onRunScenario(s.id)}
            disabled={loading || disabled}
            aria-label={`Run scenario: ${s.title}`}
            title={s.description}
          >
            <span className="scenario-button-label">{s.shortLabel}</span>
            <span className="scenario-button-desc">{s.title}</span>
          </button>
        ))}
      </div>
      <details className="demo-examples">
        <summary>Example free-text questions</summary>
        <ul>
          {DEMO_SCENARIOS.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                className="example-question"
                onClick={() => onFillQuestion(s.question)}
              >
                {s.question}
              </button>
              {s.exampleQuestions.length > 0 && (
                <ul className="example-aliases">
                  {s.exampleQuestions.map((ex) => (
                    <li key={ex}>
                      <button
                        type="button"
                        className="example-question"
                        onClick={() => onFillQuestion(ex)}
                      >
                        {ex}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      </details>
    </section>
  )
}
