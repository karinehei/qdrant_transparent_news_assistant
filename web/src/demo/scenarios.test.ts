import { describe, expect, it } from 'vitest'
import {
  DEMO_SCENARIOS,
  findScenario,
  getScenarioById,
  UNSUPPORTED_ANSWER,
} from './scenarios'
import { demoMatching } from './adapter'
import { formatScore } from '../utils/formatScore'

describe('demo scenarios', () => {
  it('provides exactly four selectable scenarios', () => {
    expect(DEMO_SCENARIOS).toHaveLength(4)
    expect(DEMO_SCENARIOS.map((s) => s.id)).toEqual([
      'supported',
      'insufficient',
      'citation-warning',
      'prompt-injection',
    ])
  })

  it('matches canonical and example questions for scenario selection', () => {
    const supported = getScenarioById('supported')!
    expect(findScenario(supported.question)?.id).toBe('supported')
    expect(findScenario('riverside park renovation')?.id).toBe('supported')
    expect(findScenario('  City Council Park Decision  ')?.id).toBe('supported')
  })

  it('builds supported answers with consistent citation labels and source ids', () => {
    const result = demoMatching.buildScenarioResult('supported')
    const labels = result.response.sources.map((s) => s.label)
    expect(labels).toEqual(['S1', 'S2'])
    for (const hit of result.response.hits) {
      expect(labels).toContain(hit.source_label)
    }
    expect(result.response.answer).toMatch(/\(S1\)/)
    expect(result.response.answer).toMatch(/\(S2\)/)
    expect(result.demo?.scenarioId).toBe('supported')
  })

  it('returns insufficient-evidence messaging for that scenario', () => {
    const result = demoMatching.buildScenarioResult('insufficient')
    expect(result.response.answer.toLowerCase()).toMatch(/cannot answer|insufficient/)
    expect(result.response.warnings.some((w) => /insufficient/i.test(w))).toBe(true)
    expect(result.response.hits.some((h) => h.rerank_score === 0)).toBe(true)
  })

  it('makes the citation-warning defect explicit', () => {
    const result = demoMatching.buildScenarioResult('citation-warning')
    expect(result.response.warnings.join(' ')).toMatch(/unsupported claim|intentional/i)
    expect(result.response.answer).toMatch(/40%/)
    expect(result.demo?.explanation).toMatch(/intentional/i)
  })

  it('explains simulated prompt-injection handling', () => {
    const result = demoMatching.buildScenarioResult('prompt-injection')
    expect(result.response.hits.some((h) => /ignore previous instructions/i.test(h.text ?? ''))).toBe(
      true,
    )
    expect(result.response.warnings.join(' ')).toMatch(/injection/i)
    expect(result.demo?.explanation).toMatch(/not executed|simulated/i)
  })

  it('does not return an unrelated canned answer for unmatched free-text', () => {
    const result = demoMatching.buildFromQuestion('What is the capital of France?')
    expect(result.response.answer).toBe(UNSUPPORTED_ANSWER)
    expect(result.demo?.unsupported).toBe(true)
    expect(result.response.sources).toHaveLength(0)
  })

  it('formats zero scores correctly', () => {
    expect(formatScore(0)).toBe('0.000')
    expect(formatScore(undefined)).toBe('n/a')
    expect(formatScore(null)).toBe('n/a')
  })
})
