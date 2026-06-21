import { openDb, queryRows } from "./db.js";

/**
 * Example read script — top fantasy-relevant performers.
 * Run: npm run query   (after at least `npm run ingest -- players player_stats`)
 *
 * Adapt the SQL freely; this is just to confirm the DB is queryable and to
 * show the shape of the data. Analytics proper can live in a separate repo
 * that points at this same .duckdb file.
 */
async function main(): Promise<void> {
  const conn = await openDb();

  const tables = await queryRows<{ name: string }>(
    conn,
    "SELECT table_name AS name FROM information_schema.tables WHERE table_schema = 'main' ORDER BY 1;",
  );
  console.log("Tables:", tables.map((t) => t.name).join(", ") || "(none — run `npm run ingest` first)");

  if (tables.some((t) => t.name === "player_stats")) {
    console.log("\nTop 10 receivers by receiving yards (latest season in DB):\n");
    const rows = await queryRows(
      conn,
      `
      WITH latest AS (SELECT max(season) AS s FROM player_stats)
      SELECT
        player_display_name AS player,
        recent_team         AS team,
        sum(receptions)     AS rec,
        sum(receiving_yards) AS rec_yds,
        sum(receiving_tds)  AS rec_td
      FROM player_stats, latest
      WHERE season = latest.s
      GROUP BY 1, 2
      ORDER BY rec_yds DESC
      LIMIT 10;
      `,
    );
    console.table(rows);
  }

  conn.closeSync();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
