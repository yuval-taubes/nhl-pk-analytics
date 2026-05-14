using Microsoft.Extensions.Logging;
using NhlPkIngest.Models;
using static NhlPkIngest.Services.ZoneEntryDetector;

namespace NhlPkIngest.Services;

/// <summary>
/// Tracks possessions through a game's play-by-play events.
/// A possession starts with a zone entry, offensive zone faceoff win, or turnover in OZ.
/// It ends with a clear, goal, stoppage, or change of possession.
/// </summary>
public class PossessionTracker
{
    private readonly ILogger<PossessionTracker> _logger;

    public PossessionTracker(ILogger<PossessionTracker> logger)
    {
        _logger = logger;
    }

    public List<Possession> ExtractPossessions(
        List<ProcessedEvent> events,
        int gameId,
        int homeTeamId,
        string strengthFilter)
    {
        var possessions = new List<Possession>();
        Possession? currentPossession = null;
        int? previousTeamId = null;
        ProcessedEvent? lastMatchingEvent = null;

        for (int i = 0; i < events.Count; i++)
        {
            var evt = events[i];

            // Strength changes break the possession window for this filtered pass.
            if (!MatchesStrength(evt, strengthFilter))
            {
                if (currentPossession != null && lastMatchingEvent != null)
                {
                    currentPossession.EndType = "STRENGTH_CHANGE";
                    currentPossession.EndEventId = lastMatchingEvent.EventId;
                    currentPossession.EndEventOriginalIdx = lastMatchingEvent.OriginalEventIdx;
                    FinalizePossession(currentPossession, events);
                    possessions.Add(currentPossession);
                    currentPossession = null;
                }

                previousTeamId = null;
                continue;
            }

            lastMatchingEvent = evt;

            // Handle faceoffs - always start a new possession
            if (evt.EventType?.Equals("faceoff", StringComparison.OrdinalIgnoreCase) == true)
            {
                // Close current possession if one exists
                if (currentPossession != null)
                {
                    currentPossession.EndEventId = evt.EventId;
                    currentPossession.EndEventOriginalIdx = evt.OriginalEventIdx;
                    currentPossession.EndType = "STOPPAGE";
                    FinalizePossession(currentPossession, events);
                    possessions.Add(currentPossession);
                    _logger.LogDebug("Closed possession (faceoff): Team {TeamId}, Events {Start}-{End}",
                        currentPossession.TeamId, currentPossession.StartEventId, currentPossession.EndEventId);
                }

                // Start new possession for the team that won the faceoff (only if in OZ)
                if (evt.Zone == "OZ" && evt.EventTeamId != null)
                {
                    _logger.LogDebug("OZ faceoff detected for team {TeamId} at event {Idx}, strength={Str}",
                        evt.EventTeamId, evt.OriginalEventIdx, evt.Strength);

                    currentPossession = CreatePossession(gameId, evt, strengthFilter,
                        "FACEOFF_START");
                    _logger.LogDebug("Started possession (OZ faceoff): Team {TeamId}, Event {EventId}",
                        evt.EventTeamId, evt.EventId);
                }
                else
                {
                    currentPossession = null;
                }

                previousTeamId = evt.EventTeamId;
                continue;
            }

            // Check for zone entries
            var entryResult = i > 0 && MatchesStrength(events[i - 1], strengthFilter)
                ? DetectZoneEntry(events, i, evt.EventTeamId ?? -1, homeTeamId)
                : null;

            if (entryResult != null)
            {
                _logger.LogDebug("Zone entry detected: type {Type} for team {TeamId} at event {Idx}, strength={Str}",
                    entryResult.Value.classification, evt.EventTeamId, evt.OriginalEventIdx, evt.Strength);
                var (classification, _, _) = entryResult.Value;

                // If same team already has possession, this is a re-entry - update entry info
                if (currentPossession != null && currentPossession.TeamId == evt.EventTeamId)
                {
                    currentPossession.EntryType = classification switch
                    {
                        EntryClassification.ControlledCarry => "CONTROLLED",
                        EntryClassification.ControlledPass => "CONTROLLED",
                        EntryClassification.DumpIn => "DUMP_IN",
                        _ => currentPossession.EntryType
                    };
                    currentPossession.EntryX = evt.XNorm;
                    currentPossession.EntryY = evt.YNorm;
                    currentPossession.StartZone = "OZ";
                }
                else
                {
                    // New zone entry - close old possession, start new one
                    if (currentPossession != null)
                    {
                        currentPossession.EndEventId = evt.EventId;
                        currentPossession.EndEventOriginalIdx = evt.OriginalEventIdx;
                        currentPossession.EndType = "CLEAR";
                        FinalizePossession(currentPossession, events);
                        possessions.Add(currentPossession);
                        _logger.LogDebug("Closed possession (zone entry by other team): Team {TeamId}",
                            currentPossession.TeamId);
                    }

                    string entryType = classification switch
                    {
                        EntryClassification.ControlledCarry => "CONTROLLED",
                        EntryClassification.ControlledPass => "CONTROLLED",
                        EntryClassification.DumpIn => "DUMP_IN",
                        _ => "CONTROLLED"
                    };

                    currentPossession = CreatePossession(gameId, evt, strengthFilter, entryType);
                    currentPossession.EntryX = evt.XNorm;
                    currentPossession.EntryY = evt.YNorm;
                    currentPossession.StartZone = "OZ";
                    _logger.LogDebug("Started possession (zone entry): Team {TeamId}, Type {EntryType}, Event {EventId}",
                        evt.EventTeamId, entryType, evt.EventId);
                }

                previousTeamId = evt.EventTeamId;
                continue;
            }

            // Handle turnover in OZ - starts a new possession for the other team
            if (evt.Zone == "OZ" && IsTakeaway(evt.EventType) &&
                currentPossession?.TeamId != evt.EventTeamId && evt.EventTeamId != null)
            {
                if (currentPossession != null)
                {
                    currentPossession.EndEventId = evt.EventId;
                    currentPossession.EndEventOriginalIdx = evt.OriginalEventIdx;
                    currentPossession.EndType = "TURNOVER";
                    FinalizePossession(currentPossession, events);
                    possessions.Add(currentPossession);
                }

                currentPossession = CreatePossession(gameId, evt, strengthFilter, "TURNOVER");
                currentPossession.EntryX = evt.XNorm;
                currentPossession.EntryY = evt.YNorm;
                currentPossession.StartZone = "OZ";
                _logger.LogDebug("Started possession (OZ turnover): Team {TeamId}, Event {EventId}",
                    evt.EventTeamId, evt.EventId);

                previousTeamId = evt.EventTeamId;
                continue;
            }

            // Track shots and goals within current possession
            if (currentPossession != null && evt.EventTeamId == currentPossession.TeamId)
            {
                if (IsShotEvent(evt.EventType))
                {
                    currentPossession.ShotCount++;

                    if (evt.EventType?.Equals("goal", StringComparison.OrdinalIgnoreCase) == true)
                    {
                        currentPossession.GoalCount++;
                        currentPossession.EndType = "GOAL";
                        currentPossession.EndEventId = evt.EventId;
                        currentPossession.EndEventOriginalIdx = evt.OriginalEventIdx;
                        FinalizePossession(currentPossession, events);
                        possessions.Add(currentPossession);
                        _logger.LogDebug("Closed possession (goal): Team {TeamId}, Events {Start}-{End}",
                            currentPossession.TeamId, currentPossession.StartEventId, currentPossession.EndEventId);
                        currentPossession = null;
                        continue;
                    }
                }
            }

            // Check for possession-ending events
            if (currentPossession != null)
            {
                bool possessionEnded = false;
                string endReason = "";

                // Clear: detected by zone transition pattern (OZ to outside OZ, same team)
                if (IsZoneExitClear(events, i, currentPossession.TeamId, homeTeamId))
                {
                    endReason = "CLEAR";
                    possessionEnded = true;
                }

                // Stoppage
                if (!possessionEnded && IsStoppage(evt.EventType))
                {
                    endReason = "STOPPAGE";
                    possessionEnded = true;
                }

                // Change of possession in OZ
                if (!possessionEnded &&
                    IsChangeOfPossession(evt.EventType ?? "", evt.EventTeamId, previousTeamId) &&
                    evt.Zone == "OZ")
                {
                    endReason = "TURNOVER";
                    possessionEnded = true;
                }

                // Penalty drawn - ends possession
                if (!possessionEnded &&
                    evt.EventType?.Equals("penalty", StringComparison.OrdinalIgnoreCase) == true)
                {
                    endReason = "PENALTY";
                    possessionEnded = true;
                }

                if (possessionEnded)
                {
                    currentPossession.EndType = endReason;
                    currentPossession.EndEventId = evt.EventId;
                    currentPossession.EndEventOriginalIdx = evt.OriginalEventIdx;
                    FinalizePossession(currentPossession, events);
                    possessions.Add(currentPossession);
                    _logger.LogDebug("Closed possession ({Reason}): Team {TeamId}, Events {Start}-{End}",
                        endReason, currentPossession.TeamId, currentPossession.StartEventId, currentPossession.EndEventId);
                    currentPossession = null;
                }
            }

            previousTeamId = evt.EventTeamId;
        }

        // Close any open possession at end of game
        if (currentPossession != null)
        {
            currentPossession.EndType = "STOPPAGE";
            currentPossession.EndEventId = lastMatchingEvent?.EventId ?? currentPossession.EndEventId;
            currentPossession.EndEventOriginalIdx = lastMatchingEvent?.OriginalEventIdx ?? currentPossession.EndEventOriginalIdx;
            FinalizePossession(currentPossession, events);
            possessions.Add(currentPossession);
            _logger.LogDebug("Closed possession (end of game): Team {TeamId}", currentPossession.TeamId);
        }

        // Filter out possessions with no meaningful activity
        possessions = possessions
            .Where(p => p.ShotCount > 0 || p.DurationSeconds > 5 || p.EndType == "GOAL")
            .ToList();

        _logger.LogInformation("Extracted {Count} possessions for game {GameId}, strength {Strength}",
            possessions.Count, gameId, strengthFilter);

        return possessions;
    }

    private static Possession CreatePossession(int gameId, ProcessedEvent startEvent,
        string strength, string entryType)
    {
        return new Possession
        {
            GameId = gameId,
            TeamId = startEvent.EventTeamId!.Value,
            StartEventId = startEvent.EventId,
            StartEventOriginalIdx = startEvent.OriginalEventIdx,
            EndEventId = startEvent.EventId,
            EndEventOriginalIdx = startEvent.OriginalEventIdx,
            Strength = strength,
            EntryType = entryType,
            EntryX = startEvent.XNorm,
            EntryY = startEvent.YNorm,
            StartZone = startEvent.Zone ?? "OZ",
            DurationSeconds = 0,
            ShotCount = 0,
            GoalCount = 0,
            XgSum = 0
        };
    }

    private static void FinalizePossession(Possession possession, List<ProcessedEvent> events)
    {
        possession.EndType ??= "STOPPAGE";
        // Compute actual duration from events
        var startEvent = events.FirstOrDefault(e => e.EventId == possession.StartEventId);
        var endEvent = events.FirstOrDefault(e => e.EventId == possession.EndEventId);

        if (startEvent != null && endEvent != null)
        {
            if (startEvent.Period == endEvent.Period)
            {
                possession.DurationSeconds = endEvent.PeriodTimeSeconds - startEvent.PeriodTimeSeconds;
            }
            else
            {
                // Cross-period: 20 minutes per full period gap + remaining time
                int periodGap = endEvent.Period - startEvent.Period;
                possession.DurationSeconds = (periodGap * 1200) +
                    endEvent.PeriodTimeSeconds - startEvent.PeriodTimeSeconds;
            }

            // Sanity check - cap at reasonable max (5 min for a single possession)
            if (possession.DurationSeconds > 300)
                possession.DurationSeconds = 300;
            if (possession.DurationSeconds < 0)
                possession.DurationSeconds = 0;
        }
    }

    // --- Event classification helpers ---

    private static bool MatchesStrength(ProcessedEvent evt, string strengthFilter)
    {
        if (evt.Strength == strengthFilter || evt.Strength == "PK")
            return true;

        return string.IsNullOrEmpty(evt.Strength) && IsStoppage(evt.EventType);
    }

    private static bool IsShotEvent(string? eventType)
    {
        if (string.IsNullOrEmpty(eventType)) return false;

        return eventType switch
        {
            "shot-on-goal" => true,
            "goal" => true,
            "missed-shot" => true,
            "blocked-shot" => true,
            "shot" => true,
            _ => false
        };
    }

    /// <summary>
    /// Detects a clear by checking if the puck moved from OZ to outside OZ
    /// while the same team maintained possession. Event-type agnostic.
    /// </summary>
    private static bool IsZoneExitClear(List<ProcessedEvent> events, int currentIdx, int teamId, int homeTeamId)
    {
        if (currentIdx < 1) return false;

        var current = events[currentIdx];
        var prev = events[currentIdx - 1];

        // Do not count shots from outside the OZ as clears.
        if (current.EventType is "shot-on-goal" or "missed-shot" or "blocked-shot")
            return false;

        // Zone labels are relative to the event team, so use them only when the same
        // team owns both events. Otherwise, fall back to absolute rink coordinates.
        if (prev.EventTeamId == teamId &&
            current.EventTeamId == teamId &&
            prev.Zone == "OZ" &&
            current.Zone != "OZ" &&
            !string.IsNullOrEmpty(current.Zone))
        {
            return true;
        }

        // Coordinate fallback: puck crossed the attacking blue line outward.
        if (prev.XNorm != null && current.XNorm != null && prev.EventTeamId == teamId)
        {
            bool isHomeTeam = teamId == homeTeamId;
            bool prevInOZ = isHomeTeam
                ? prev.XNorm >= CoordinateNormalizer.AwayBlueLine
                : prev.XNorm <= CoordinateNormalizer.HomeBlueLine;
            bool currOutsideOZ = isHomeTeam
                ? current.XNorm < CoordinateNormalizer.AwayBlueLine
                : current.XNorm > CoordinateNormalizer.HomeBlueLine;

            if (prevInOZ && currOutsideOZ)
                return true;
        }

        return false;
    }
    private static bool IsClearEvent(string? eventType)
    {
        if (string.IsNullOrEmpty(eventType)) return false;
        return eventType switch
        {
            "clear" => true,
            "cleared" => true,
            "dump-out" => true,
            "puck-out-of-bounds" => true,
            "puck-out-of-play" => true,
            "icing" => true,
            "offside" => true,
            "puck-in-crowd" => true,
            "puck-in-netting" => true,
            "puck-in-benches" => true,
            _ => false
        };
    }
    private static bool IsTakeaway(string? eventType)
    {
        return eventType?.Equals("takeaway", StringComparison.OrdinalIgnoreCase) == true;
    }
}
