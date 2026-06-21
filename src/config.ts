import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "..");

/** Path to the DuckDB database file. Override with DB_PATH env var. */
export const DB_PATH = process.env.DB_PATH ?? resolve(repoRoot, "data/fantasy.duckdb");

/**
 * Seasons to ingest for season-partitioned datasets (pbp, rosters, etc.).
 * Override with SEASONS env var, e.g. `SEASONS=2020,2021,2022 npm run ingest`.
 * Single-file datasets (players, games) ignore this.
 */
export const SEASONS: number[] = (process.env.SEASONS?.split(",").map((s) => Number(s.trim())) ?? defaultSeasons())
  .filter((s) => Number.isInteger(s) && s >= 1999);

function defaultSeasons(): number[] {
  // Last 5 completed-ish seasons. Bump the end as new seasons land.
  const end = 2024;
  const start = end - 4;
  return Array.from({ length: end - start + 1 }, (_, i) => start + i);
}
