"""
Configuration for NHL PK Analytics Pipeline.

Database settings default to the local development values but can be
overridden with environment variables. Do not commit real credentials.
"""

import os

# Database connection
DB_CONFIG = {
    'host': os.getenv('NHL_DB_HOST', 'localhost'),
    'database': os.getenv('NHL_DB_NAME', 'nhl_pk_analytics'),
    'user': os.getenv('NHL_DB_USER', 'postgres'),
    'password': os.getenv('NHL_DB_PASSWORD', ''),
    'port': int(os.getenv('NHL_DB_PORT', '5432'))
}

# Rink dimensions (NHL standard)
RINK_LENGTH_FT = 200
RINK_WIDTH_FT = 85

# Validation thresholds
class Thresholds:
    # Sample size minimums
    MIN_POSSESSIONS_FOR_ATT = 100
    MIN_GAMES_FOR_BOOTSTRAP = 30
    MIN_POSSESSION_SAMPLE = 50
    
    # Join inflation
    MAX_JOIN_INFLATION = 3.0
    
    # Coordinate validation
    X_MIN = 0
    X_MAX = 200
    Y_MIN = 0
    Y_MAX = 85
    
    # Possession quality
    MAX_POSSESSION_ISSUE_RATE = 0.20
    
    # Propensity score overlap
    MIN_OVERLAP_PROPORTION = 0.50
    
    # xG model validation
    MIN_XG_AUC = 0.70
    MAX_CALIBRATION_ERROR = 0.10
    
    # Bootstrap
    N_BOOTSTRAP = 500
    BOOTSTRAP_CI = 95

# Paths
MODEL_PATH = 'models/trained/xg_model.joblib'
RUNS_DIR = 'runs'
