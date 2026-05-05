-- Core reference tables
CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY,
    name VARCHAR(100),
    abbreviation VARCHAR(3)
);

CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY,
    full_name VARCHAR(100),
    position VARCHAR(2)
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
CREATE TABLE IF NOT EXISTS shots (
    shot_id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES events(event_id),
    possession_id INTEGER REFERENCES possessions(possession_id),
    shooter_id INTEGER REFERENCES players(player_id),
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
    PRIMARY KEY (event_id, player_id)
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

-- Indexes
CREATE INDEX IF NOT EXISTS idx_events_game ON events(game_id, event_idx);
CREATE INDEX IF NOT EXISTS idx_events_strength ON events(strength) WHERE strength IN ('4v5', '3v5', '5v4', '5v3');
CREATE INDEX IF NOT EXISTS idx_possessions_game_team ON possessions(game_id, team_id);
CREATE INDEX IF NOT EXISTS idx_possessions_entry ON possessions(entry_type) WHERE entry_type IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_shots_possession ON shots(possession_id);