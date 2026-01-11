export interface SourceItem {
  label: string;
  title: string;
  url?: string;
  published_at?: string;
  publisher?: string;
}

export interface HitItem {
  uid?: string;
  source_label: string;
  title?: string;
  url?: string;
  published_at?: string;
  score?: number;
  rerank_score?: number;
  text?: string;
}

export interface ChatResponse {
  answer: string;
  sources: SourceItem[];
  hits: HitItem[];
  run_id: number;
  warnings: string[];
}

export interface ChatRequest {
  question: string;
}

export interface RunItem {
  id: number;
  created_at: string;
  question: string;
  model: string;
}
