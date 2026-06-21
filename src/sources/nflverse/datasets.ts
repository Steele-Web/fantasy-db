/**
 * Registry of nflverse datasets.
 *
 * nflverse publishes data as parquet/csv assets on GitHub releases
 * (https://github.com/nflverse/nflverse-data/releases). DuckDB's httpfs
 * extension reads these URLs directly, so ingest is just a remote read into
 * a local table — no manual download/parse step.
 *
 * To add a dataset: confirm the asset URL exists on the releases page, then
 * add an entry below. Season-partitioned sets supply one file per season;
 * we read them as a list so a single table spans all configured seasons.
 */

const RELEASE = "https://github.com/nflverse/nflverse-data/releases/download";

export interface Dataset {
  /** DuckDB table name this dataset lands in. */
  name: string;
  description: string;
  format: "parquet" | "csv";
  /** True if there is one file per season; false for a single all-time file. */
  perSeason: boolean;
  /** Build the list of source URLs for the configured seasons. */
  urls: (seasons: number[]) => string[];
}

export const DATASETS: Dataset[] = [
  {
    name: "players",
    description: "Master player table (ids, bio, positions) across all eras",
    format: "parquet",
    perSeason: false,
    urls: () => [`${RELEASE}/players/players.parquet`],
  },
  {
    name: "games",
    description: "Game/schedule results, lines and metadata (all seasons)",
    format: "csv",
    perSeason: false,
    urls: () => ["https://github.com/nflverse/nfldata/raw/master/data/games.csv"],
  },
  {
    name: "player_stats",
    description: "Weekly player stats (offense), per season",
    format: "parquet",
    perSeason: true,
    urls: (seasons) => seasons.map((y) => `${RELEASE}/player_stats/player_stats_${y}.parquet`),
  },
  {
    name: "pbp",
    description: "Play-by-play (nflfastR), per season — large",
    format: "parquet",
    perSeason: true,
    urls: (seasons) => seasons.map((y) => `${RELEASE}/pbp/play_by_play_${y}.parquet`),
  },
  {
    name: "rosters",
    description: "Season rosters, per season",
    format: "parquet",
    perSeason: true,
    urls: (seasons) => seasons.map((y) => `${RELEASE}/rosters/roster_${y}.parquet`),
  },
  {
    name: "weekly_rosters",
    description: "Week-by-week rosters, per season",
    format: "parquet",
    perSeason: true,
    urls: (seasons) => seasons.map((y) => `${RELEASE}/weekly_rosters/roster_weekly_${y}.parquet`),
  },
  {
    name: "snap_counts",
    description: "Player snap counts, per season",
    format: "parquet",
    perSeason: true,
    urls: (seasons) => seasons.map((y) => `${RELEASE}/snap_counts/snap_counts_${y}.parquet`),
  },
  {
    name: "depth_charts",
    description: "Team depth charts, per season",
    format: "parquet",
    perSeason: true,
    urls: (seasons) => seasons.map((y) => `${RELEASE}/depth_charts/depth_charts_${y}.parquet`),
  },
  {
    name: "injuries",
    description: "Injury reports, per season",
    format: "parquet",
    perSeason: true,
    urls: (seasons) => seasons.map((y) => `${RELEASE}/injuries/injuries_${y}.parquet`),
  },
];

export function getDataset(name: string): Dataset | undefined {
  return DATASETS.find((d) => d.name === name);
}
