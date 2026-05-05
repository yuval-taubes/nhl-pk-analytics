namespace NhlPkIngest.Services;

/// <summary>
/// Normalizes NHL API coordinates to a consistent 200x85 rink perspective.
/// All normalized coordinates are from the HOME team's perspective:
///   - Home net at (0, 42.5) — left side
///   - Away net at (200, 42.5) — right side
///   - x increases from home net to away net
///   - Offensive zone for home team: x > 150 (approximately)
///   - Offensive zone for away team: x < 50 (approximately)
/// </summary>
public class CoordinateNormalizer
{
    // NHL rink dimensions in feet
    public const int RinkLength = 200;
    public const int RinkWidth = 85;

    // Blue line positions (from each end boards)
    public const int BlueLineOffset = 75; // 75ft from end boards to blue line
    // Blue lines are at x=75 and x=125 from home perspective
    public const int HomeBlueLine = BlueLineOffset;      // 75
    public const int AwayBlueLine = RinkLength - BlueLineOffset; // 125

    // Neutral zone bounds
    public const int NeutralZoneStart = HomeBlueLine;   // 75
    public const int NeutralZoneEnd = AwayBlueLine;     // 125

    /// <summary>
    /// Normalizes a single coordinate pair for a given period and team context.
    /// </summary>
    /// <param name="x">Original API x coordinate</param>
    /// <param name="y">Original API y coordinate</param>
    /// <param name="period">Period number (1-4+)</param>
    /// <param name="isHomeEvent">Is the event from the home team's perspective?</param>
    /// <param name="xNorm">Normalized x (home perspective)</param>
    /// <param name="yNorm">Normalized y (home perspective)</param>
    public static void Normalize(int? x, int? y, int period, bool isHomeEvent,
        out int? xNorm, out int? yNorm)
    {
        if (x == null || y == null)
        {
            xNorm = null;
            yNorm = null;
            return;
        }

        int rawX = x.Value;
        int rawY = y.Value;

        // The NHL API sometimes returns negative coordinates or coordinates > 100
        // indicating a flipped rink. Normalize to 0-200 for x, 0-85 for y.
        // Raw API typically returns: x: -100 to 100, y: -42 to 42
        // But can also return: x: 0 to 200, y: 0 to 85

        // First, determine the API's coordinate system
        int absX = Math.Abs(rawX);
        int absY = Math.Abs(rawY);

        // Detect which scale the API is using
        if (absX <= 100 && absY <= 42)
        {
            // Old scale: -100..100, -42..42
            // Center ice is (0,0). Convert to 0-200, 0-85
            double xScaled = ((rawX / 100.0) * (RinkLength / 2.0)) + (RinkLength / 2.0);
            double yScaled = ((rawY / 42.0) * (RinkWidth / 2.0)) + (RinkWidth / 2.0);
            rawX = (int)Math.Round(xScaled);
            rawY = (int)Math.Round(yScaled);
        }
        else if (absX <= 200 && absY <= 85)
        {
            // Already in 0-200, 0-85 scale
            // No scaling needed
        }
        else
        {
            // Unknown scale, attempt to clamp
            rawX = Math.Clamp(rawX, 0, RinkLength);
            rawY = Math.Clamp(rawY, 0, RinkWidth);
        }

        // Now determine if we need to flip based on period and team context
        // In period 1 and 3: home team attacks right-to-left, away team attacks left-to-right
        // In period 2 and OT: teams switch sides
        // We want everything from HOME perspective (home net at x=0, away net at x=200)

        bool flipX = false;
        bool flipY = false;

        // For home events in period 1/3/OT1/OT3: no flip (home attacks left side, x increasing)
        // For home events in period 2/OT2: flip (home attacks right side)
        // For away events in period 1/3/OT1/OT3: flip (away attacks right, but we want home perspective)
        // For away events in period 2/OT2: no flip

        int effectivePeriod = period;
        // Overtime pattern continues: period 5 (OT1) same as period 1, period 6 (OT2) same as period 2
        bool periodOdd = (effectivePeriod % 2 == 1);

        if (isHomeEvent)
        {
            // Home event: home attacks x=200 in odd periods, x=0 in even periods
            // We want home to always attack x=0, so flip in even periods
            flipX = !periodOdd;
        }
        else
        {
            // Away event: away attacks x=200 in even periods, x=0 in odd periods (from home perspective)
            // We want away to always attack x=200 from home perspective
            // So flip in odd periods
            flipX = periodOdd;
        }

        // Y-coordinate flipping: home bench is typically on one side
        // NHL API: positive y is typically towards home bench
        // We keep y as-is (0-85 from home bench side to penalty box side)

        if (flipX)
        {
            xNorm = RinkLength - rawX;
        }
        else
        {
            xNorm = rawX;
        }

        if (flipY)
        {
            yNorm = RinkWidth - rawY;
        }
        else
        {
            yNorm = rawY;
        }

        // Clamp to rink boundaries
        xNorm = Math.Clamp(xNorm.Value, 0, RinkLength);
        yNorm = Math.Clamp(yNorm.Value, 0, RinkWidth);
    }

    /// <summary>
    /// Determines the zone based on normalized x coordinate (home perspective).
    /// </summary>
    public static string DetermineZone(int? xNorm, int? teamId, int homeTeamId)
    {
        if (xNorm == null) return "NZ"; // Default to neutral if no coordinate

        int x = xNorm.Value;

        if (x <= HomeBlueLine)
        {
            // Left side of rink (home end)
            return teamId == homeTeamId ? "DZ" : "OZ";
        }
        else if (x >= AwayBlueLine)
        {
            // Right side of rink (away end)
            return teamId == homeTeamId ? "OZ" : "DZ";
        }
        else
        {
            return "NZ";
        }
    }

    /// <summary>
    /// Checks if the puck crossed into the offensive zone (for zone entry detection).
    /// </summary>
    public static bool CrossedOffensiveBlueLine(int? prevXN, int? currXN, int teamId, int homeTeamId)
    {
        if (prevXN == null || currXN == null) return false;

        bool isHome = teamId == homeTeamId;
        double blueLine = isHome ? AwayBlueLine : HomeBlueLine;
        double prevDistance = Math.Abs(prevXN.Value - blueLine);
        double currDistance = Math.Abs(currXN.Value - blueLine);

        // Puck was in neutral zone and now in offensive zone
        bool wasInNeutral = prevXN.Value > HomeBlueLine && prevXN.Value < AwayBlueLine;
        bool nowInOffensive = isHome ? currXN.Value >= AwayBlueLine : currXN.Value <= HomeBlueLine;

        return wasInNeutral && nowInOffensive;
    }
}