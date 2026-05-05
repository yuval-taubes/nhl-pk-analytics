using NhlPkIngest.Models;
namespace NhlPkIngest.Services;

/// <summary>
/// Detects zone entries from play-by-play event sequences.
/// Zone entries are NOT explicit in the NHL API. We derive them using:
/// - Coordinate heuristics (puck crosses blue line from NZ to OZ)
/// - Event type context (carry, pass, dump)
/// - No intervening stoppage or change of possession
/// </summary>
public class ZoneEntryDetector
{
    public enum EntryClassification
    {
        None,
        ControlledCarry,   // Player carries puck across blue line
        ControlledPass,    // Pass across blue line to teammate
        DumpIn             // Puck dumped into zone, no immediate possession
    }

    /// <summary>
    /// Analyzes a window of events to detect and classify a zone entry.
    /// </summary>
    public static (EntryClassification classification, int entryEventIdx, int? carrierId)?
        DetectZoneEntry(List<ProcessedEvent> events, int currentIdx, int teamId, int homeTeamId)
    {
        if (currentIdx < 2) return null;

        var current = events[currentIdx];
        var prev = events[currentIdx - 1];
        var twoBack = events[currentIdx - 2];

        // Must be an offensive zone event for the team in question
        if (current.EventTeamId != teamId) return null;

        // Check if previous event was in neutral zone
        bool prevWasNeutral = prev.EventTeamId == teamId &&
                               prev.Zone == "NZ";

        // Check for coordinates crossing the blue line
        bool crossedBlueLine = CoordinateNormalizer.CrossedOffensiveBlueLine(
            prev.XNorm, current.XNorm, teamId, homeTeamId);

        if (!crossedBlueLine && !prevWasNeutral) return null;

        // Classify the entry type
        var classification = ClassifyEntry(events, currentIdx, twoBack, prev, current, teamId);

        if (classification == EntryClassification.None) return null;

        return (classification, current.EventIdx, current.EventTeamId);
    }

    private static EntryClassification ClassifyEntry(
        List<ProcessedEvent> events, int currentIdx,
        ProcessedEvent twoBack, ProcessedEvent prev,
        ProcessedEvent current, int teamId)
    {
        string currType = current.EventType ?? "";
        string prevType = prev.EventType ?? "";

        // Check for dump-in patterns
        bool isDumpIn = currType.Equals("dumpin", StringComparison.OrdinalIgnoreCase) ||
                        currType.Equals("dump", StringComparison.OrdinalIgnoreCase) ||
                        (prevType.Equals("dumpin", StringComparison.OrdinalIgnoreCase) &&
                         currType.Equals("takeaway", StringComparison.OrdinalIgnoreCase));

        if (isDumpIn)
            return EntryClassification.DumpIn;

        // Controlled carry: player carries puck across (no pass event)
        bool isCarry = (currType.Equals("carry", StringComparison.OrdinalIgnoreCase) ||
                         currType.Equals("zoneentry", StringComparison.OrdinalIgnoreCase) ||
                         currType.Equals("rush", StringComparison.OrdinalIgnoreCase)) &&
                        !prevType.Contains("pass", StringComparison.OrdinalIgnoreCase);

        if (isCarry)
            return EntryClassification.ControlledCarry;

        // Controlled pass: pass event that crosses the blue line
        bool isPass = currType.Equals("pass", StringComparison.OrdinalIgnoreCase) ||
                      prevType.Equals("pass", StringComparison.OrdinalIgnoreCase);

        if (isPass && prev.EventTeamId == teamId)
            return EntryClassification.ControlledPass;

        // Shot on goal from neutral zone that crosses (rare, typically dump)
        if ((currType.Equals("shot-on-goal", StringComparison.OrdinalIgnoreCase) ||
             currType.Equals("missed-shot", StringComparison.OrdinalIgnoreCase)) &&
            prev.Zone == "NZ" && prev.EventTeamId == teamId)
        {
            return EntryClassification.DumpIn;
        }

        // Generic: if the puck moves from NZ to OZ without a stoppage/possession change,
        // assume it's some form of entry
        if (current.Zone == "OZ" && prev.Zone == "NZ" && prev.EventTeamId == teamId)
        {
            // Default to controlled if there's a takeaway or pass context
            if (currType.Contains("takeaway", StringComparison.OrdinalIgnoreCase) ||
                currType.Contains("poss", StringComparison.OrdinalIgnoreCase))
                return EntryClassification.ControlledCarry;
            return EntryClassification.ControlledPass;
        }

        return EntryClassification.None;
    }

    /// <summary>
    /// Determines if an event represents a change of possession.
    /// </summary>
    public static bool IsChangeOfPossession(string eventType, int? currentTeamId, int? previousTeamId)
    {
        if (currentTeamId == null || previousTeamId == null) return false;

        // Direct possession change events
        var possessionChangeEvents = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "takeaway", "giveaway", "blocked-shot", "hit",
            "puck-recovery", "takeaway-home", "takeaway-away"
        };

        if (possessionChangeEvents.Contains(eventType ?? ""))
            return true;

        // Team change without explicit possession event
        if (currentTeamId != previousTeamId)
        {
            // Only count as possession change if it's not a faceoff (faceoffs start new possessions)
            if (!eventType?.Equals("faceoff", StringComparison.OrdinalIgnoreCase) == true)
                return true;
        }

        return false;
    }

    /// <summary>
    /// Checks if an event is a stoppage (whistle, period end).
    /// </summary>
    public static bool IsStoppage(string? eventType)
    {
        var stoppageEvents = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "stoppage", "period-end", "period-start", "game-end",
            "tv-timeout", "timeout", "official-timeout", "whistle",
            "penalty", "delayed-penalty"
        };

        return stoppageEvents.Contains(eventType ?? "");
    }
}