-- Fact tables (marts): the per-event / per-snapshot measures that the apps query.
-- dbt models upsert into these via INSERT OR REPLACE on the natural keys below.
-- The snapshotted tables (vegas, projections, rankings, status) are append-only
-- because their history is what makes the backtester valid.

-- The big one: per-player per-game unified stats
CREATE TABLE IF NOT EXISTS fct_player_game_stats (
    player_id           INTEGER NOT NULL,
    game_id             VARCHAR NOT NULL,
    season              INTEGER NOT NULL,
    week                INTEGER NOT NULL,
    team_id             INTEGER,
    opponent_id         INTEGER,
    position            VARCHAR,

    -- Snap counts / usage
    offensive_snaps     INTEGER,
    offensive_snap_pct  DECIMAL(5,2),
    routes_run          INTEGER,

    -- Passing
    pass_attempts       INTEGER,
    pass_completions    INTEGER,
    pass_yards          INTEGER,
    pass_tds            INTEGER,
    interceptions       INTEGER,
    sacks_taken         INTEGER,
    pass_air_yards      INTEGER,
    pass_epa            DECIMAL(7,3),
    cpoe                DECIMAL(5,2),            -- completion % over expected (NGS)

    -- Rushing
    rush_attempts       INTEGER,
    rush_yards          INTEGER,
    rush_tds            INTEGER,
    rush_yards_before_contact DECIMAL(6,2),     -- NGS
    rush_yards_over_expected  DECIMAL(6,2),     -- NGS

    -- Receiving
    targets             INTEGER,
    receptions          INTEGER,
    rec_yards           INTEGER,
    rec_tds             INTEGER,
    air_yards           INTEGER,
    yac                 INTEGER,
    target_share        DECIMAL(5,2),
    air_yards_share     DECIMAL(5,2),
    avg_separation      DECIMAL(4,2),           -- NGS
    avg_cushion         DECIMAL(4,2),           -- NGS

    -- Red zone / high-value
    rz_carries          INTEGER,
    rz_targets          INTEGER,
    inside_5_carries    INTEGER,
    inside_5_targets    INTEGER,

    -- Misc
    fumbles             INTEGER,
    fumbles_lost        INTEGER,
    two_pt_conversions  INTEGER,

    -- Lineage
    ingested_at         TIMESTAMP DEFAULT current_timestamp,

    PRIMARY KEY (player_id, game_id)
);

-- Per-team per-game (for matchup analysis)
CREATE TABLE IF NOT EXISTS fct_team_game_stats (
    team_id             INTEGER NOT NULL,
    game_id             VARCHAR NOT NULL,
    season              INTEGER NOT NULL,
    week                INTEGER NOT NULL,
    opponent_id         INTEGER,
    is_home             BOOLEAN,

    -- Team offense
    points              INTEGER,
    total_yards         INTEGER,
    pass_yards          INTEGER,
    rush_yards          INTEGER,
    plays               INTEGER,
    seconds_per_play    DECIMAL(4,2),
    pass_rate           DECIMAL(5,2),
    pace_neutral        DECIMAL(5,2),

    -- Team defense (what they allowed)
    points_allowed      INTEGER,
    yards_allowed       INTEGER,
    pass_yards_allowed  INTEGER,
    rush_yards_allowed  INTEGER,
    sacks               INTEGER,
    interceptions       INTEGER,

    PRIMARY KEY (team_id, game_id)
);

-- Vegas lines (historical, multiple snapshots per game)
CREATE TABLE IF NOT EXISTS fct_vegas_lines (
    game_id             VARCHAR NOT NULL,
    snapshot_at         TIMESTAMP NOT NULL,
    sportsbook          VARCHAR NOT NULL,
    spread_home         DECIMAL(4,1),
    spread_away         DECIMAL(4,1),
    total               DECIMAL(4,1),
    home_moneyline      INTEGER,
    away_moneyline      INTEGER,
    home_implied_total  DECIMAL(4,1),           -- derived: (total/2) - (spread_home/2)
    away_implied_total  DECIMAL(4,1),
    PRIMARY KEY (game_id, snapshot_at, sportsbook)
);

-- Projections (yours + external, append-only with snapshots)
CREATE TABLE IF NOT EXISTS fct_projections (
    snapshot_date       DATE NOT NULL,
    source              VARCHAR NOT NULL,        -- 'fantasypros_ecr', 'my_model_v1', etc.
    player_id           INTEGER NOT NULL,
    season              INTEGER NOT NULL,
    week                INTEGER NOT NULL,        -- 0 = season-long
    scoring_format      VARCHAR NOT NULL,        -- 'ppr', 'half_ppr', 'standard'
    projected_points    DECIMAL(5,2),
    floor               DECIMAL(5,2),
    ceiling             DECIMAL(5,2),

    -- Component projections (useful for debugging your model)
    proj_pass_yards     DECIMAL(6,2),
    proj_pass_tds       DECIMAL(4,2),
    proj_rush_yards     DECIMAL(6,2),
    proj_rush_tds       DECIMAL(4,2),
    proj_receptions     DECIMAL(5,2),
    proj_rec_yards      DECIMAL(6,2),
    proj_rec_tds        DECIMAL(4,2),

    PRIMARY KEY (snapshot_date, source, player_id, season, week, scoring_format)
);

-- Expert rankings (also snapshotted)
CREATE TABLE IF NOT EXISTS fct_rankings (
    snapshot_date       DATE NOT NULL,
    source              VARCHAR NOT NULL,
    player_id           INTEGER NOT NULL,
    season              INTEGER NOT NULL,
    week                INTEGER NOT NULL,        -- 0 = season-long / draft
    scoring_format      VARCHAR NOT NULL,
    position            VARCHAR,
    overall_rank        INTEGER,
    position_rank       INTEGER,
    tier                INTEGER,
    PRIMARY KEY (snapshot_date, source, player_id, season, week, scoring_format)
);

-- Injuries / status (snapshotted because they change)
CREATE TABLE IF NOT EXISTS fct_player_status (
    snapshot_date       DATE NOT NULL,
    player_id           INTEGER NOT NULL,
    season              INTEGER,
    week                INTEGER,
    practice_status     VARCHAR,                 -- DNP, Limited, Full
    game_status         VARCHAR,                 -- Questionable, Doubtful, Out, IR
    injury_description  VARCHAR,
    PRIMARY KEY (snapshot_date, player_id)
);

-- Play-by-play stays in Parquet, attached as a view when needed (it's big and
-- rarely joined with the marts). The view is created/refreshed by the pbp staging
-- step once files exist — DuckDB binds a view's schema eagerly, so it can't be
-- defined here against an empty glob. See db.connection.refresh_pbp_view().
