"""
Rink geometry helpers for the normalized 200 x 85 coordinate system.

Coordinates are stored from the home team's rink perspective:
- home net: x=11
- away net: x=189
- y=42.5 is the center of the rink width

For shot quality work, the safest target net is the net on the same rink half
as the shot location. The ingestion normalizes coordinates for team/period
context, so a fixed home/away-team target net can measure many shots to the
wrong end of the rink.
"""

import numpy as np

RINK_LENGTH_FT = 200
RINK_WIDTH_FT = 85

HOME_NET_X = 11
HOME_NET_Y = 42.5

AWAY_NET_X = 189
AWAY_NET_Y = 42.5


def is_shooting_home_net(x_norm):
    """Return True when the shot is closer to the home net."""
    return abs(x_norm - HOME_NET_X) <= abs(x_norm - AWAY_NET_X)


def target_net_x(x_norm):
    """Return target net x-coordinate inferred from shot location."""
    return HOME_NET_X if is_shooting_home_net(x_norm) else AWAY_NET_X


def calculate_distance_to_net(x_norm, y_norm, shooting_home_net=None):
    """Calculate Euclidean distance from shot location to target net."""
    if shooting_home_net is None:
        shooting_home_net = is_shooting_home_net(x_norm)
    net_x = HOME_NET_X if shooting_home_net else AWAY_NET_X
    return np.sqrt((x_norm - net_x) ** 2 + (y_norm - HOME_NET_Y) ** 2)


def calculate_shot_angle(x_norm, y_norm, shooting_home_net=None):
    """
    Calculate shot angle in degrees from the target net center line.

    0 degrees is straight on from the slot; larger values indicate sharper
    lateral angle. This matches the SQL expression used by the xG model:
    atan2(abs(y - net_y), abs(x - net_x)).
    """
    if shooting_home_net is None:
        shooting_home_net = is_shooting_home_net(x_norm)
    net_x = HOME_NET_X if shooting_home_net else AWAY_NET_X
    dx = abs(x_norm - net_x)
    dy = abs(y_norm - HOME_NET_Y)
    return np.degrees(np.arctan2(dy, dx))


TARGET_NET_X_SQL = """
CASE
    WHEN s.x_norm IS NULL THEN NULL
    WHEN ABS(s.x_norm - 11) <= ABS(s.x_norm - 189) THEN 11
    ELSE 189
END
"""
