-- Core reference tables
CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY,
    name VARCHAR(100),
    abbreviation VARCHAR(3)
);

CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY,
    full_name VARCHAR(100),
    position VARCHAR(5)  -- was VARCHAR(2), widened for 'NA'
);

CREATE TABLE IF NOT EXISTS games (
    game_id INTEGER PRIMARY KEY,
    season VARCHAR(8),
    game_date DATE,
    home_team_id INTEGER REFERENCES teams(team_id),
    away_team_id INTEGER REFERENCES teams(team_id),
    home_score INTEGER,
    away_score INTEGER
);

-- Tracks which team a player was on for each game
CREATE TABLE IF NOT EXISTS game_players (
    game_id INTEGER REFERENCES games(game_id),
    player_id INTEGER REFERENCES players(player_id),
    team_id INTEGER REFERENCES teams(team_id),
    PRIMARY KEY (game_id, player_id)
);


-- Raw play-by-play events
CREATE TABLE IF NOT EXISTS events (
    event_id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(game_id),
    event_idx INTEGER,
    period INTEGER,
    period_time_seconds INTEGER,
    event_type VARCHAR(50),
    event_team_id INTEGER REFERENCES teams(team_id),
    x INTEGER,
    y INTEGER,
    x_norm INTEGER,
    y_norm INTEGER,
    zone VARCHAR(20),
    strength VARCHAR(10),
    description TEXT,
    home_skaters INTEGER,
    away_skaters INTEGER
);

-- Derived possessions
CREATE TABLE IF NOT EXISTS possessions (
    possession_id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(game_id),
    team_id INTEGER REFERENCES teams(team_id),
    start_event_id INTEGER REFERENCES events(event_id),
    end_event_id INTEGER REFERENCES events(event_id),
    strength VARCHAR(10),
    entry_type VARCHAR(20),
    entry_x INTEGER,
    entry_y INTEGER,
    start_zone VARCHAR(20),
    end_type VARCHAR(30),
    duration_seconds NUMERIC(5,1),
    shot_count INTEGER,
    goal_count INTEGER,
    xg_sum NUMERIC(6,4)
);

-- Expected goals and shot details
-- Expected goals and shot details
CREATE TABLE IF NOT EXISTS shots (
    shot_id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES events(event_id),
    possession_id INTEGER REFERENCES possessions(possession_id) NULL,
    shooter_id INTEGER REFERENCES players(player_id) NULL,
    x INTEGER,
    y INTEGER,
    x_norm INTEGER,
    y_norm INTEGER,
    shot_type VARCHAR(30),
    is_goal BOOLEAN,
    xg NUMERIC(5,4)
);

-- On-ice players per event
CREATE TABLE IF NOT EXISTS event_players (
    event_id INTEGER REFERENCES events(event_id),
    player_id INTEGER REFERENCES players(player_id),
    team_id INTEGER REFERENCES teams(team_id),
    is_home BOOLEAN,
    original_event_idx INTEGER
);


-- Raw NHL shiftchart segments, one row per player shift
CREATE TABLE IF NOT EXISTS game_shifts (
    shift_id SERIAL PRIMARY KEY,
    source_shift_id INTEGER NOT NULL,
    game_id INTEGER REFERENCES games(game_id),
    player_id INTEGER REFERENCES players(player_id),
    team_id INTEGER REFERENCES teams(team_id),
    is_home BOOLEAN,
    period INTEGER,
    shift_number INTEGER,
    start_time VARCHAR(5),
    end_time VARCHAR(5),
    duration VARCHAR(5),
    start_seconds INTEGER,
    end_seconds INTEGER,
    start_game_seconds INTEGER,
    end_game_seconds INTEGER,
    duration_seconds NUMERIC(6,1)
);

-- Durable source audit. Missing rows and failed requests are different states.
CREATE TABLE IF NOT EXISTS game_shift_source_status (
    game_id INTEGER PRIMARY KEY REFERENCES games(game_id) ON DELETE CASCADE,
    source_status VARCHAR(30) NOT NULL CHECK (source_status IN ('available', 'missing_empty_response', 'request_error', 'not_checked')),
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    row_count INTEGER NOT NULL DEFAULT 0 CHECK (row_count >= 0),
    endpoint_url TEXT NOT NULL,
    http_status_code INTEGER,
    error_message TEXT,
    CHECK ((source_status = 'available' AND row_count > 0) OR (source_status <> 'available' AND row_count = 0))
);

-- Full shift-derived on-ice players per play-by-play event
CREATE TABLE IF NOT EXISTS event_on_ice_players (
    event_id INTEGER REFERENCES events(event_id),
    player_id INTEGER REFERENCES players(player_id),
    team_id INTEGER REFERENCES teams(team_id),
    is_home BOOLEAN,
    is_goalie BOOLEAN,
    is_skater BOOLEAN,
    original_event_idx INTEGER
);

-- Event-level shift-derived manpower and comparison to NHL situationCode parsing
CREATE TABLE IF NOT EXISTS event_manpower (
    event_id INTEGER PRIMARY KEY REFERENCES events(event_id),
    original_event_idx INTEGER,
    home_skaters_shift INTEGER,
    away_skaters_shift INTEGER,
    home_goalie_id INTEGER REFERENCES players(player_id) NULL,
    away_goalie_id INTEGER REFERENCES players(player_id) NULL,
    home_goalie_pulled BOOLEAN,
    away_goalie_pulled BOOLEAN,
    strength_state_shift VARCHAR(10),
    strength_code_shift VARCHAR(3),
    matches_situation_code BOOLEAN
);
-- Pre-computed causal model outputs
CREATE TABLE IF NOT EXISTS causal_results (
    result_id SERIAL PRIMARY KEY,
    team_id INTEGER REFERENCES teams(team_id),
    season VARCHAR(8),
    treatment_desc VARCHAR(100),
    att NUMERIC(6,4),
    ci_lower NUMERIC(6,4),
    ci_upper NUMERIC(6,4),
    sample_size_treated INTEGER,
    sample_size_control INTEGER,
    computed_at TIMESTAMP DEFAULT NOW()
);

-- Clustered goal-against sequences
CREATE TABLE IF NOT EXISTS ga_sequences (
    sequence_id SERIAL PRIMARY KEY,
    team_id INTEGER REFERENCES teams(team_id),
    game_id INTEGER REFERENCES games(game_id),
    event_id INTEGER REFERENCES events(event_id),
    sequence_events JSONB,
    cluster_id INTEGER,
    tactical_label VARCHAR(100),
    frequency_rank INTEGER
);

-- Player scouting model outputs
CREATE TABLE IF NOT EXISTS player_scouting (
    scout_id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(player_id),
    season VARCHAR(8),
    model_name VARCHAR(50),
    metric_name VARCHAR(50),
    metric_value NUMERIC(8,4),
    percentile INTEGER,
    sample_size INTEGER,
    computed_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_events_game ON events(game_id, event_idx);
CREATE INDEX IF NOT EXISTS idx_events_strength ON events(strength) WHERE strength IN ('4v5', '3v5', '5v4', '5v3');
CREATE INDEX IF NOT EXISTS idx_game_players_game ON game_players(game_id);
CREATE INDEX IF NOT EXISTS idx_possessions_game_team ON possessions(game_id, team_id);
CREATE INDEX IF NOT EXISTS idx_possessions_start_event ON possessions(start_event_id);
CREATE INDEX IF NOT EXISTS idx_possessions_end_event ON possessions(end_event_id);
CREATE INDEX IF NOT EXISTS idx_possessions_entry ON possessions(entry_type) WHERE entry_type IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_shots_event ON shots(event_id);
CREATE INDEX IF NOT EXISTS idx_shots_possession ON shots(possession_id);
CREATE INDEX IF NOT EXISTS idx_event_players_event ON event_players(event_id);
CREATE INDEX IF NOT EXISTS idx_game_shifts_game ON game_shifts(game_id, period, start_seconds, end_seconds);
CREATE INDEX IF NOT EXISTS idx_game_shifts_player ON game_shifts(player_id);
CREATE INDEX IF NOT EXISTS idx_game_shift_source_status ON game_shift_source_status(source_status, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_on_ice_event ON event_on_ice_players(event_id);
CREATE INDEX IF NOT EXISTS idx_event_on_ice_player ON event_on_ice_players(player_id);
CREATE INDEX IF NOT EXISTS idx_event_manpower_strength ON event_manpower(strength_code_shift);
CREATE INDEX IF NOT EXISTS idx_player_scouting_model ON player_scouting(model_name);
CREATE INDEX IF NOT EXISTS idx_player_scouting_player ON player_scouting(player_id);

-- Make re-ingestion idempotent for existing databases too. CREATE TABLE IF NOT EXISTS
-- will not update old FK definitions, so replace the relevant constraints explicitly.
ALTER TABLE game_players DROP CONSTRAINT IF EXISTS game_players_game_id_fkey;
ALTER TABLE game_players ADD CONSTRAINT game_players_game_id_fkey
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE;

ALTER TABLE game_players DROP CONSTRAINT IF EXISTS game_players_player_id_fkey;
ALTER TABLE game_players ADD CONSTRAINT game_players_player_id_fkey
    FOREIGN KEY (player_id) REFERENCES players(player_id);

ALTER TABLE game_players DROP CONSTRAINT IF EXISTS game_players_team_id_fkey;
ALTER TABLE game_players ADD CONSTRAINT game_players_team_id_fkey
    FOREIGN KEY (team_id) REFERENCES teams(team_id);

ALTER TABLE events DROP CONSTRAINT IF EXISTS events_game_id_fkey;
ALTER TABLE events ADD CONSTRAINT events_game_id_fkey
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE;

ALTER TABLE events DROP CONSTRAINT IF EXISTS events_event_team_id_fkey;
ALTER TABLE events ADD CONSTRAINT events_event_team_id_fkey
    FOREIGN KEY (event_team_id) REFERENCES teams(team_id);

ALTER TABLE possessions DROP CONSTRAINT IF EXISTS possessions_game_id_fkey;
ALTER TABLE possessions ADD CONSTRAINT possessions_game_id_fkey
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE;

ALTER TABLE possessions DROP CONSTRAINT IF EXISTS possessions_team_id_fkey;
ALTER TABLE possessions ADD CONSTRAINT possessions_team_id_fkey
    FOREIGN KEY (team_id) REFERENCES teams(team_id);

ALTER TABLE possessions DROP CONSTRAINT IF EXISTS possessions_start_event_id_fkey;
ALTER TABLE possessions ADD CONSTRAINT possessions_start_event_id_fkey
    FOREIGN KEY (start_event_id) REFERENCES events(event_id) ON DELETE CASCADE;

ALTER TABLE possessions DROP CONSTRAINT IF EXISTS possessions_end_event_id_fkey;
ALTER TABLE possessions ADD CONSTRAINT possessions_end_event_id_fkey
    FOREIGN KEY (end_event_id) REFERENCES events(event_id) ON DELETE CASCADE;

ALTER TABLE shots DROP CONSTRAINT IF EXISTS shots_event_id_fkey;
ALTER TABLE shots ADD CONSTRAINT shots_event_id_fkey
    FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE;

ALTER TABLE shots DROP CONSTRAINT IF EXISTS shots_possession_id_fkey;
ALTER TABLE shots ADD CONSTRAINT shots_possession_id_fkey
    FOREIGN KEY (possession_id) REFERENCES possessions(possession_id) ON DELETE SET NULL;

ALTER TABLE shots DROP CONSTRAINT IF EXISTS shots_shooter_id_fkey;
ALTER TABLE shots ADD CONSTRAINT shots_shooter_id_fkey
    FOREIGN KEY (shooter_id) REFERENCES players(player_id);

ALTER TABLE event_players DROP CONSTRAINT IF EXISTS event_players_event_id_fkey;
ALTER TABLE event_players ADD CONSTRAINT event_players_event_id_fkey
    FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE;

ALTER TABLE event_players DROP CONSTRAINT IF EXISTS event_players_player_id_fkey;
ALTER TABLE event_players ADD CONSTRAINT event_players_player_id_fkey
    FOREIGN KEY (player_id) REFERENCES players(player_id);

ALTER TABLE event_players DROP CONSTRAINT IF EXISTS event_players_team_id_fkey;
ALTER TABLE event_players ADD CONSTRAINT event_players_team_id_fkey
    FOREIGN KEY (team_id) REFERENCES teams(team_id);

ALTER TABLE event_players DROP CONSTRAINT IF EXISTS event_players_unique_event_player;
ALTER TABLE event_players ADD CONSTRAINT event_players_unique_event_player
    UNIQUE (event_id, player_id);

WITH ranked_player_scouting_duplicates AS (
    SELECT
        scout_id,
        ROW_NUMBER() OVER (
            PARTITION BY player_id, season, model_name, metric_name
            ORDER BY computed_at DESC NULLS LAST, scout_id DESC
        ) AS duplicate_rank
    FROM player_scouting
)
DELETE FROM player_scouting ps
USING ranked_player_scouting_duplicates ranked
WHERE ps.scout_id = ranked.scout_id
  AND ranked.duplicate_rank > 1;

ALTER TABLE player_scouting DROP CONSTRAINT IF EXISTS player_scouting_unique_metric;
ALTER TABLE player_scouting ADD CONSTRAINT player_scouting_unique_metric
    UNIQUE (player_id, season, model_name, metric_name);
ALTER TABLE game_shifts DROP CONSTRAINT IF EXISTS game_shifts_game_id_fkey;
ALTER TABLE game_shifts ADD CONSTRAINT game_shifts_game_id_fkey
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE;

ALTER TABLE game_shifts DROP CONSTRAINT IF EXISTS game_shifts_player_id_fkey;
ALTER TABLE game_shifts ADD CONSTRAINT game_shifts_player_id_fkey
    FOREIGN KEY (player_id) REFERENCES players(player_id);

ALTER TABLE game_shifts DROP CONSTRAINT IF EXISTS game_shifts_team_id_fkey;
ALTER TABLE game_shifts ADD CONSTRAINT game_shifts_team_id_fkey
    FOREIGN KEY (team_id) REFERENCES teams(team_id);

ALTER TABLE game_shifts DROP CONSTRAINT IF EXISTS game_shifts_unique_source_shift;
ALTER TABLE game_shifts ADD CONSTRAINT game_shifts_unique_source_shift
    UNIQUE (game_id, source_shift_id);

ALTER TABLE event_on_ice_players DROP CONSTRAINT IF EXISTS event_on_ice_players_event_id_fkey;
ALTER TABLE event_on_ice_players ADD CONSTRAINT event_on_ice_players_event_id_fkey
    FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE;

ALTER TABLE event_on_ice_players DROP CONSTRAINT IF EXISTS event_on_ice_players_player_id_fkey;
ALTER TABLE event_on_ice_players ADD CONSTRAINT event_on_ice_players_player_id_fkey
    FOREIGN KEY (player_id) REFERENCES players(player_id);

ALTER TABLE event_on_ice_players DROP CONSTRAINT IF EXISTS event_on_ice_players_team_id_fkey;
ALTER TABLE event_on_ice_players ADD CONSTRAINT event_on_ice_players_team_id_fkey
    FOREIGN KEY (team_id) REFERENCES teams(team_id);

ALTER TABLE event_on_ice_players DROP CONSTRAINT IF EXISTS event_on_ice_unique_event_player;
ALTER TABLE event_on_ice_players ADD CONSTRAINT event_on_ice_unique_event_player
    UNIQUE (event_id, player_id);

ALTER TABLE event_manpower DROP CONSTRAINT IF EXISTS event_manpower_event_id_fkey;
ALTER TABLE event_manpower ADD CONSTRAINT event_manpower_event_id_fkey
    FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE;

ALTER TABLE event_manpower DROP CONSTRAINT IF EXISTS event_manpower_home_goalie_id_fkey;
ALTER TABLE event_manpower ADD CONSTRAINT event_manpower_home_goalie_id_fkey
    FOREIGN KEY (home_goalie_id) REFERENCES players(player_id);

ALTER TABLE event_manpower DROP CONSTRAINT IF EXISTS event_manpower_away_goalie_id_fkey;
ALTER TABLE event_manpower ADD CONSTRAINT event_manpower_away_goalie_id_fkey
    FOREIGN KEY (away_goalie_id) REFERENCES players(player_id);

-- Source-covered player-event features. This is an auditable feature layer,
-- not a player-impact estimate.
CREATE OR REPLACE VIEW pk_shift_player_event_features AS
WITH shifts_with_rest AS (
    SELECT
        gs.*,
        GREATEST(0, gs.start_game_seconds - LAG(gs.end_game_seconds) OVER (
            PARTITION BY gs.game_id, gs.player_id
            ORDER BY gs.start_game_seconds, gs.source_shift_id
        )) AS rest_before_shift_seconds
    FROM game_shifts gs
)
SELECT
    e.game_id, e.event_id, eoip.original_event_idx, e.period,
    e.period_time_seconds, e.event_type, e.event_team_id,
    eoip.player_id, eoip.team_id, eoip.is_home,
    p.full_name AS player_name, p.position, t.abbreviation AS team,
    swr.source_shift_id, swr.shift_number,
    swr.duration_seconds AS shift_duration_seconds,
    swr.rest_before_shift_seconds,
    e.period_time_seconds - swr.start_seconds AS shift_age_seconds,
    CASE WHEN eoip.is_home
        THEN e.home_skaters < e.away_skaters
        ELSE e.away_skaters < e.home_skaters
    END AS is_penalty_killing,
    gsss.source_status, gsss.checked_at AS source_checked_at
FROM event_on_ice_players eoip
JOIN events e ON e.event_id = eoip.event_id
JOIN shifts_with_rest swr
  ON swr.game_id = e.game_id
 AND swr.player_id = eoip.player_id
 AND swr.period = e.period
 AND swr.start_seconds <= e.period_time_seconds
 AND e.period_time_seconds < swr.end_seconds
JOIN game_shift_source_status gsss
  ON gsss.game_id = e.game_id AND gsss.source_status = 'available'
JOIN players p ON p.player_id = eoip.player_id
JOIN teams t ON t.team_id = eoip.team_id
WHERE eoip.is_skater;
