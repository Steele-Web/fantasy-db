import { DuckDBInstance, type DuckDBConnection } from "@duckdb/node-api";
import { mkdir } from "node:fs/promises";
import { dirname } from "node:path";
import { DB_PATH } from "./config.js";

/**
 * Open (or create) the DuckDB database and return a ready connection with the
 * httpfs extension loaded — required to read nflverse files over HTTP.
 */
export async function openDb(path: string = DB_PATH): Promise<DuckDBConnection> {
  await mkdir(dirname(path), { recursive: true });
  const instance = await DuckDBInstance.create(path);
  const conn = await instance.connect();
  await conn.run("INSTALL httpfs; LOAD httpfs;");
  return conn;
}

/** Run a query and return rows as plain objects. */
export async function queryRows<T = Record<string, unknown>>(
  conn: DuckDBConnection,
  sql: string,
): Promise<T[]> {
  const reader = await conn.runAndReadAll(sql);
  return reader.getRowObjects() as T[];
}
