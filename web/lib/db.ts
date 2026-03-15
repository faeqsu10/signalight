import Database from "better-sqlite3";
import path from "path";

const STORAGE_PATH = path.join(process.cwd(), "..", "storage");

export interface LLMAnalysis {
  ticker: string;
  name: string;
  verdict: string;
  confidence: number;
  reasoning: string;
  model: string;
  created_at: string;
}

export interface Sentiment {
  ticker: string;
  name: string;
  sentiment: string;
  confidence: number;
  summary: string;
  headlines_json: string;
  created_at: string;
}

export function getLatestLLMAnalysis(ticker: string): LLMAnalysis | null {
  const dbFiles = [
    "signalight_us.db",
    "signalight_meanrev.db",
    "signalight_swing.db",
    "signalight_us_meanrev.db"
  ];

  for (const dbFile of dbFiles) {
    try {
      const dbPath = path.join(STORAGE_PATH, dbFile);
      const db = new Database(dbPath, { readonly: true });
      
      const query = `
        SELECT ticker, name, verdict, confidence, reasoning, model, created_at
        FROM llm_analysis
        WHERE ticker = ?
        ORDER BY created_at DESC
        LIMIT 1
      `;
      
      const row = db.prepare(query).get(ticker) as LLMAnalysis | undefined;
      db.close();
      
      if (row) {
        return row;
      }
    } catch (err) {
      continue;
    }
  }

  return null;
}

export function getLatestSentiment(ticker: string): Sentiment | null {
  const dbFiles = [
    "signalight_us.db",
    "signalight_meanrev.db",
    "signalight_swing.db",
    "signalight_us_meanrev.db"
  ];

  for (const dbFile of dbFiles) {
    try {
      const dbPath = path.join(STORAGE_PATH, dbFile);
      const db = new Database(dbPath, { readonly: true });
      
      const query = `
        SELECT ticker, name, sentiment, confidence, summary, headlines_json, created_at
        FROM news_sentiment
        WHERE ticker = ?
        ORDER BY created_at DESC
        LIMIT 1
      `;
      
      const row = db.prepare(query).get(ticker) as Sentiment | undefined;
      db.close();
      
      if (row) {
        return row;
      }
    } catch (err) {
      continue;
    }
  }

  return null;
}
