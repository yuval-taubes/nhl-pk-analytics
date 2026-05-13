"""
Rink geometry calculations with proper home/away net handling.
"""

import numpy as np

# Rink dimensions - NHL standard (renamed for clarity)
RINK_LENGTH_FT = 200  # goal line to goal line
RINK_WIDTH_FT = 85    # boards to boards

# Net positions in normalized coordinates (home perspective)
HOME_NET_X = 11    # Home goal line is 11ft from end boards
HOME_NET_Y = 42.5  # Center of net (half of 85ft width)

AWAY_NET_X = 189   # Away goal line (200 - 11)
AWAY_NET_Y = 42.5  # Center of net


def calculate_distance_to_net(x_norm, y_norm, is_shooting_home_net):
    """
    Calculate Euclidean distance from shot location to target net.
    
    Args:
        x_norm, y_norm: Shot coordinates in normalized 200x85 rink
        is_shooting_home_net: True if shooting at home team's net (x=11)
    
    Returns:
        Distance in feet
    """
    if is_shooting_home_net:
        net_x, net_y = HOME_NET_X, HOME_NET_Y
    else:
        net_x, net_y = AWAY_NET_X, AWAY_NET_Y
    
    return np.sqrt((x_norm - net_x) ** 2 + (y_norm - net_y) ** 2)


def calculate_shot_angle(x_norm, y_norm, is_shooting_home_net):
    """
    Calculate shot angle in degrees from goal line.
    
    0° = straight on (in close)
    90° = parallel to goal line (sharp angle from boards)
    
    Args:
        x_norm, y_norm: Shot coordinates
        is_shooting_home_net: True if shooting at home net
    
    Returns:
        Angle in degrees
    """
    if is_shooting_home_net:
        net_x, net_y = HOME_NET_X, HOME_NET_Y
    else:
        net_x, net_y = AWAY_NET_X, AWAY_NET_Y
    
    dx = net_x - x_norm
    dy = net_y - y_norm
    
    angle_rad = np.arctan2(abs(dx), abs(dy)) if dy != 0 else np.pi/2
    
    return np.degrees(angle_rad)