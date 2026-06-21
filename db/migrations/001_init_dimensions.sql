-- Dimension tables: the stable "nouns" of the model — players, teams,
-- franchises, games — plus the crosswalk that ties every source's IDs back to
-- our internal surrogate player_id.

-- Internal player registry
CREATE TABLE IF NOT EXISTS dim_players (
    player_id        INTEGER PRIMARY KEY,        -- internal surrogate key
    full_name        VARCHAR NOT NULL,
    first_name       VARCHAR,
    last_name        VARCHAR,
    position         VARCHAR,                    -- QB, RB, WR, TE, K, DST
    birthdate        DATE,
    height_inches    INTEGER,
    weight_lbs       INTEGER,
    college          VARCHAR,
    draft_year       INTEGER,
    draft_round      INTEGER,
    draft_pick       INTEGER,
    debut_season     INTEGER,
    status           VARCHAR,                    -- active, retired, ir, etc.
    created_at       TIMESTAMP DEFAULT current_timestamp,
    updated_at       TIMESTAMP DEFAULT current_timestamp
);

-- Cross-reference IDs from every source to our internal ID
CREATE TABLE IF NOT EXISTS player_id_crosswalk (
    player_id        INTEGER NOT NULL,
    source           VARCHAR NOT NULL,           -- 'pfr', 'gsis', 'espn', 'sleeper', 'yahoo', 'fantasypros'
    source_id        VARCHAR NOT NULL,
    PRIMARY KEY (source, source_id)
);

-- Franchise-level identity (groups across relocations)
CREATE TABLE IF NOT EXISTS dim_franchises (
    franchise_id     INTEGER PRIMARY KEY,
    canonical_name   VARCHAR                     -- 'Raiders', 'Chargers'
);

-- Team in a given season
CREATE TABLE IF NOT EXISTS dim_teams (
    team_id          INTEGER PRIMARY KEY,
    franchise_id     INTEGER REFERENCES dim_franchises(franchise_id),
    season           INTEGER NOT NULL,
    abbr             VARCHAR NOT NULL,           -- 'KC', 'LV', 'WAS'
    city             VARCHAR,
    name             VARCHAR,
    conference       VARCHAR,                    -- AFC/NFC
    division         VARCHAR,                    -- East/West/North/South
    UNIQUE (season, abbr)
);

-- Roster: which players were on which teams in which season/week
CREATE TABLE IF NOT EXISTS player_team_history (
    player_id        INTEGER NOT NULL,
    team_id          INTEGER NOT NULL,
    season           INTEGER NOT NULL,
    week_start       INTEGER NOT NULL,
    week_end         INTEGER,                    -- NULL = still on team
    jersey_number    INTEGER,
    depth_chart_pos  VARCHAR,
    PRIMARY KEY (player_id, season, week_start)
);

-- Games
CREATE TABLE IF NOT EXISTS dim_games (
    game_id          VARCHAR PRIMARY KEY,        -- '2024_01_BAL_KC'
    season           INTEGER NOT NULL,
    week             INTEGER NOT NULL,
    season_type      VARCHAR,                    -- REG, POST, PRE
    game_date        DATE,
    kickoff_time     TIMESTAMP,
    home_team_id     INTEGER REFERENCES dim_teams(team_id),
    away_team_id     INTEGER REFERENCES dim_teams(team_id),
    home_score       INTEGER,
    away_score       INTEGER,
    stadium          VARCHAR,
    surface          VARCHAR,                    -- grass, turf
    roof             VARCHAR,                    -- dome, outdoors, retractable
    weather_temp_f   INTEGER,
    weather_wind_mph INTEGER,
    weather_desc     VARCHAR
);
