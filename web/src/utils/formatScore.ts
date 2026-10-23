/** Format retrieval/rerank scores, including explicit zero. */
export function formatScore(score: number | undefined | null): string {
  if (score === undefined || score === null || Number.isNaN(score)) {
    return 'n/a'
  }
  return score.toFixed(3)
}
