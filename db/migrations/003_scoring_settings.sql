-- Configurable scoring. Apps compute fantasy points by joining stats against a
-- row here, so changing a league's rules never requires rebuilding stats. Seeded
-- with the standard formats; keep in sync with config/scoring.yaml.

CREATE TABLE IF NOT EXISTS scoring_settings (
    scoring_format      VARCHAR PRIMARY KEY,     -- 'ppr', 'half_ppr', 'standard', 'my_league'
    pass_yard_pts       DECIMAL(4,3) DEFAULT 0.04,
    pass_td_pts         DECIMAL(4,1) DEFAULT 4.0,
    pass_int_pts        DECIMAL(4,1) DEFAULT -2.0,
    rush_yard_pts       DECIMAL(4,3) DEFAULT 0.1,
    rush_td_pts         DECIMAL(4,1) DEFAULT 6.0,
    rec_pts             DECIMAL(4,1) DEFAULT 1.0,
    rec_yard_pts        DECIMAL(4,3) DEFAULT 0.1,
    rec_td_pts          DECIMAL(4,1) DEFAULT 6.0,
    fumble_lost_pts     DECIMAL(4,1) DEFAULT -2.0,
    two_pt_pts          DECIMAL(4,1) DEFAULT 2.0,
    bonus_100_rush_yds  DECIMAL(4,1) DEFAULT 0,
    bonus_100_rec_yds   DECIMAL(4,1) DEFAULT 0,
    bonus_300_pass_yds  DECIMAL(4,1) DEFAULT 0,
    te_premium          DECIMAL(4,1) DEFAULT 0
);

INSERT OR REPLACE INTO scoring_settings (scoring_format, rec_pts) VALUES
    ('ppr', 1.0),
    ('half_ppr', 0.5),
    ('standard', 0.0);
