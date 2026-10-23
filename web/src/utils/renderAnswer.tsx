import type { ReactNode } from 'react'

const CITATION_RE = /\((S\d+)\)/g

/**
 * Split answer text into paragraphs and make (S1)-style citations keyboard-operable buttons.
 */
export function renderAnswerWithCitations(
  answer: string,
  onCitationClick: (label: string) => void,
): ReactNode[] {
  return answer.split('\n').map((line, lineIdx) => {
    if (!line.trim()) {
      return <p key={`p-${lineIdx}`}>&nbsp;</p>
    }

    const nodes: ReactNode[] = []
    let last = 0
    CITATION_RE.lastIndex = 0
    let match: RegExpExecArray | null
    while ((match = CITATION_RE.exec(line)) !== null) {
      if (match.index > last) {
        nodes.push(line.slice(last, match.index))
      }
      const label = match[1]
      nodes.push(
        <button
          key={`cite-${lineIdx}-${match.index}`}
          type="button"
          className="citation-ref"
          onClick={() => onCitationClick(label)}
          aria-label={`Show source ${label}`}
        >
          ({label})
        </button>,
      )
      last = match.index + match[0].length
    }
    if (last < line.length) {
      nodes.push(line.slice(last))
    }

    return <p key={`p-${lineIdx}`}>{nodes}</p>
  })
}
