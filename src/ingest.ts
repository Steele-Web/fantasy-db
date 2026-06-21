import { openDb } from "./db.js";
import { SEASONS, DB_PATH } from "./config.js";
import { DATASETS, getDataset, type Dataset } from "./sources/nflverse/datasets.js";
import { ingestDataset } from "./sources/nflverse/ingest.js";

/**
 * Ingest CLI.
 *
 *   npm run ingest -- --list            list available datasets
 *   npm run ingest -- players games     ingest the named datasets
 *   npm run ingest:all                  ingest everything
 *   SEASONS=2022,2023 npm run ingest -- pbp
 */
async function main(): Promise<void> {
  const args = process.argv.slice(2);

  if (args.includes("--list")) {
    printList();
    return;
  }

  const all = args.includes("--all");
  const named = args.filter((a) => !a.startsWith("--"));

  let targets: Dataset[];
  if (all || named.length === 0) {
    targets = DATASETS;
    if (named.length === 0 && !all) {
      console.log("No datasets named — ingesting all. (Use --list to see options.)\n");
    }
  } else {
    targets = [];
    for (const name of named) {
      const ds = getDataset(name);
      if (!ds) {
        console.error(`Unknown dataset: "${name}". Run with --list to see options.`);
        process.exitCode = 1;
        return;
      }
      targets.push(ds);
    }
  }

  console.log(`DB:      ${DB_PATH}`);
  console.log(`Seasons: ${SEASONS.join(", ")}`);
  console.log(`Datasets: ${targets.map((d) => d.name).join(", ")}\n`);

  const conn = await openDb();
  let failures = 0;

  for (const ds of targets) {
    const label = ds.perSeason ? `${ds.name} (${SEASONS.length} seasons)` : ds.name;
    process.stdout.write(`→ ${label} … `);
    const startedAt = process.hrtime.bigint();
    try {
      const res = await ingestDataset(conn, ds, SEASONS);
      const ms = Number(process.hrtime.bigint() - startedAt) / 1e6;
      console.log(`${res.rows.toLocaleString()} rows from ${res.files} file(s) in ${(ms / 1000).toFixed(1)}s`);
    } catch (err) {
      failures++;
      console.log("FAILED");
      console.error(`  ${(err as Error).message.split("\n")[0]}`);
    }
  }

  conn.closeSync();
  console.log(`\nDone. ${targets.length - failures}/${targets.length} datasets ingested into ${DB_PATH}`);
  if (failures > 0) process.exitCode = 1;
}

function printList(): void {
  console.log("Available nflverse datasets:\n");
  for (const ds of DATASETS) {
    const tag = ds.perSeason ? "[per-season]" : "[single]   ";
    console.log(`  ${tag} ${ds.name.padEnd(16)} ${ds.description}`);
  }
  console.log("\nUsage: npm run ingest -- <name> [<name> ...]   |   npm run ingest:all");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
