"""
Rink geometry helpers for the normalized 200 x 85 coordinate system.

Coordinates are stored from the home team's rink perspective:
- home net: x=11
- away net: x=189
- y=42.5 is the center of the rink width

For shot quality work, the target net should be based on the shooting team
after ingestion has resolved `events.event_team_id` to the shooter/scorer team.
"""

import numpy as np

RINK_LENGTH_FT = 200
RINK_WIDTH_FT = 85

HOME_NET_X = 11
HOME_NET_Y = 42.5

AWAY_NET_X = 189
AWAY_NET_Y = 42.5


def is_shooting_home_net(event_team_id, home_team_id):
    """Return True when the shooting team is attacking the home net."""
    return event_team_id != home_team_id


def target_net_x(event_team_id, home_team_id):
    """Return target net x-coordinate for a shot event."""
    return HOME_NET_X if is_shooting_home_net(event_team_id, home_team_id) else AWAY_NET_X


def calculate_distance_to_net(x_norm, y_norm, shooting_home_net):
    """Calculate Euclidean distance from shot location to target net."""
    net_x = HOME_NET_X if shooting_home_net else AWAY_NET_X
    return np.sqrt((x_norm - net_x) ** 2 + (y_norm - HOME_NET_Y) ** 2)


def calculate_shot_angle(x_norm, y_norm, shooting_home_net):
    """
    Calculate shot angle in degrees from the target net center line.

    0 degrees is straight on from the slot; larger values indicate sharper
    lateral angle. This matches the SQL expression used by the xG model:
    atan2(abs(y - net_y), abs(x - net_x)).
    """
    net_x = HOME_NET_X if shooting_home_net else AWAY_NET_X
    dx = abs(x_norm - net_x)
    dy = abs(y_norm - HOME_NET_Y)
    return np.degrees(np.arctan2(dy, dx))


TARGET_NET_X_SQL = """
CASE
    WHEN e.event_team_id = g.home_team_id THEN 189
    WHEN e.event_team_id = g.away_team_id THEN 11
    ELSE NULL
END
"""
