import type { DuckDBConnection } from "@duckdb/node-api";
import { queryRows } from "../../db.js";
import type { Dataset } from "./datasets.js";

/** SQL string literal list: ['a','b'] -> "'a','b'". */
function sqlList(urls: string[]): string {
  return urls.map((u) => `'${u.replace(/'/g, "''")}'`).join(", ");
}

/**
 * Build the read expression for a dataset. We use union_by_name so season
 * files with slightly drifting schemas still stack into one table.
 */
function readExpr(ds: Dataset, urls: string[]): string {
  if (ds.format === "csv") {
    return `read_csv_auto([${sqlList(urls)}], union_by_name = true)`;
  }
  return `read_parquet([${sqlList(urls)}], union_by_name = true)`;
}

export interface IngestResult {
  name: string;
  rows: number;
  files: number;
}

/**
 * Ingest a single dataset into its own table (CREATE OR REPLACE — full refresh).
 * Returns row/file counts. Throws on read failure so the caller can report it.
 */
export async function ingestDataset(
  conn: DuckDBConnection,
  ds: Dataset,
  seasons: number[],
): Promise<IngestResult> {
  const urls = ds.urls(seasons);
  if (urls.length === 0) {
    throw new Error(`No source URLs for "${ds.name}" (no seasons configured?)`);
  }

  const expr = readExpr(ds, urls);
  await conn.run(`CREATE OR REPLACE TABLE "${ds.name}" AS SELECT * FROM ${expr};`);

  const rows = await queryRows<{ n: bigint }>(conn, `SELECT count(*) AS n FROM "${ds.name}";`);
  return { name: ds.name, rows: Number(rows[0]?.n ?? 0), files: urls.length };
}
