using Microsoft.Extensions.Logging;
using NhlPkIngest.Models;

namespace NhlPkIngest.Services;

/// <summary>
/// Orchestrates the full ingestion pipeline for a single game.
/// </summary>
public class GameIngester
{
    private readonly NhlApiClient _apiClient;
    private readonly DatabaseManager _dbManager;
    private readonly CoordinateNormalizer _normalizer;
    private readonly ZoneEntryDetector _entryDetector;
    private readonly PossessionTracker _possessionTracker;
    private readonly ILogger<GameIngester> _logger;

public GameIngester(
    NhlApiClient apiClient,
    DatabaseManager dbManager,
    ILoggerFactory loggerFactory)
{
    _apiClient = apiClient;
    _dbManager = dbManager;
    _logger = loggerFactory.CreateLogger<GameIngester>();
    _possessionTracker = new PossessionTracker(loggerFactory.CreateLogger<PossessionTracker>());
}

    public async Task<bool> IngestGameAsync(int gameId)
    {
        _logger.LogInformation("Ingesting game {GameId}...", gameId);

        var pbp = await _apiClient.GetPlayByPlayAsync(gameId);
        if (pbp == null) return false;

        // 1. Process teams
        var homeTeamId = pbp.HomeTeam!.Id;
        var awayTeamId = pbp.AwayTeam!.Id;

        var teams = new List<Team>
        {
            new Team { TeamId = homeTeamId, Name = pbp.HomeTeam.Name!, Abbreviation = pbp.HomeTeam.Abbrev! },
            new Team { TeamId = awayTeamId, Name = pbp.AwayTeam.Name!, Abbreviation = pbp.AwayTeam.Abbrev! }
        };

        // 2. Process game metadata
        var game = new Game
        {
            GameId = gameId,
            Season = pbp.Season,
            GameDate = DateOnly.TryParse(pbp.GameDate, out var d) ? d : DateOnly.MinValue,
            HomeTeamId = homeTeamId,
            AwayTeamId = awayTeamId,
            HomeScore = pbp.HomeTeam.Score ?? 0,
            AwayScore = pbp.AwayTeam.Score ?? 0
        };

        // 3. Process players from rosters
        var players = new List<Player>();
        var gamePlayers = new List<GamePlayer>();

        if (pbp.Rosters != null)
        {
            if (pbp.Rosters.Home != null)
            {
                foreach (var p in pbp.Rosters.Home)
                {
                    players.Add(new Player { PlayerId = p.PlayerId, FullName = p.FullName ?? "", Position = p.PositionCode ?? "" });
                    gamePlayers.Add(new GamePlayer { GameId = gameId, PlayerId = p.PlayerId, TeamId = homeTeamId });
                }
            }
            if (pbp.Rosters.Away != null)
            {
                foreach (var p in pbp.Rosters.Away)
                {
                    players.Add(new Player { PlayerId = p.PlayerId, FullName = p.FullName ?? "", Position = p.PositionCode ?? "" });
                    gamePlayers.Add(new GamePlayer { GameId = gameId, PlayerId = p.PlayerId, TeamId = awayTeamId });
                }
            }
        }

        // 4. Process events
        var (processedEvents, shots, eventPlayers) = ProcessEvents(
            pbp.Plays!, gameId, homeTeamId, awayTeamId);

        // 5. Derive possessions for PK strengths
        var allPossessions = new List<Possession>();
        foreach (var strength in new[] { "4v5", "3v5", "3v4" })
        {
            var possessions = _possessionTracker.ExtractPossessions(
                processedEvents, gameId, homeTeamId, strength);
            allPossessions.AddRange(possessions);
        }

        // 6. Assign possession IDs to shots
        AssignPossessionsToShots(allPossessions, shots, processedEvents);

        // 7. Bulk insert everything
        await using var conn = _dbManager.CreateConnection();
        await using var transaction = await conn.BeginTransactionAsync();

        try
        {
            // Insert in dependency order
            await _dbManager.BulkCopyTeamsAsync(teams.DistinctBy(t => t.TeamId).ToList());
            await _dbManager.BulkCopyGamesAsync(new List<Game> { game });
            await _dbManager.BulkCopyPlayersAsync(players.DistinctBy(p => p.PlayerId).ToList());
            await _dbManager.BulkCopyGamePlayersAsync(gamePlayers);

            // Events must be inserted before possessions (need event_ids)
            await _dbManager.UpsertEventsForGameAsync(gameId, processedEvents.Select(e => e.ToEvent()).ToList());

            // Now get the actual event IDs (SERIAL from DB)
            var eventIds = await _dbManager.GetEventIdsBatchAsync(gameId, processedEvents.Count);
            for (int i = 0; i < processedEvents.Count; i++)
            {
                processedEvents[i].EventId = eventIds[i];
            }

            // Update possessions with real event IDs
            foreach (var poss in allPossessions)
            {
                var startEvent = processedEvents.FirstOrDefault(e => e.OriginalEventIdx ==
                    processedEvents.First(pe => pe.EventId == poss.StartEventId).OriginalEventIdx);
                var endEvent = processedEvents.FirstOrDefault(e => e.OriginalEventIdx ==
                    processedEvents.First(pe => pe.EventId == poss.EndEventId).OriginalEventIdx);

                if (startEvent != null && endEvent != null)
                {
                    poss.StartEventId = startEvent.EventId;
                    poss.EndEventId = endEvent.EventId;
                    poss.DurationSeconds = ComputeDuration(startEvent, endEvent);
                }
            }

            await _dbManager.BulkCopyPossessionsAsync(allPossessions);

            // Update shot possession IDs
            var possessionIdMap = allPossessions.ToDictionary(
                p => p.StartEventId,
                p => p.PossessionId);

            foreach (var shot in shots)
            {
                // Find which possession this shot belongs to
                var containingPossession = allPossessions
                    .FirstOrDefault(p => shot.EventId >= p.StartEventId &&
                                         shot.EventId <= p.EndEventId &&
                                         p.TeamId == shot.ShooterTeamId);
                if (containingPossession != null)
                {
                    shot.PossessionId = containingPossession.PossessionId;
                }
            }

            // Update shot event IDs
            foreach (var shot in shots)
            {
                var pe = processedEvents.FirstOrDefault(e => e.OriginalEventIdx ==
                    processedEvents.First(pe2 => pe2.EventId == shot.EventId).OriginalEventIdx);
                if (pe != null) shot.EventId = pe.EventId;
            }

            await _dbManager.BulkCopyShotsAsync(shots);
            await _dbManager.BulkCopyEventPlayersAsync(eventPlayers);

            await transaction.CommitAsync();
            _logger.LogInformation("Game {GameId} ingested successfully: {EventCount} events, {ShotCount} shots, {PossessionCount} possessions",
                gameId, processedEvents.Count, shots.Count, allPossessions.Count);
            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to ingest game {GameId}, rolling back.", gameId);
            await transaction.RollbackAsync();
            throw;
        }
    }

    private (List<ProcessedEvent> events, List<Shot> shots, List<EventPlayer> eventPlayers)
        ProcessEvents(List<NhlPlay> plays, int gameId, int homeTeamId, int awayTeamId)
    {
        var events = new List<ProcessedEvent>();
        var shots = new List<Shot>();
        var eventPlayers = new List<EventPlayer>();

        for (int i = 0; i < plays.Count; i++)
        {
            var play = plays[i];
            var eventType = NormalizeEventType(play.TypeDescKey);

            // Normalize coordinates
            bool isHomeEvent = play.TeamId == homeTeamId;
            CoordinateNormalizer.Normalize(
                play.XCoord ?? play.Details?.XCoord,
                play.YCoord ?? play.Details?.YCoord,
                play.Period,
                isHomeEvent,
                out int? xNorm,
                out int? yNorm);

            // Determine zone
            string zone = play.ZoneCode ?? play.Details?.ZoneCode ?? "";
            if (string.IsNullOrEmpty(zone) && xNorm != null)
            {
                zone = CoordinateNormalizer.DetermineZone(xNorm, play.TeamId, homeTeamId);
            }

            // Parse time
            int periodTimeSeconds = ParseTimeInPeriod(play.TimeInPeriod);

            // Determine strength
            string strength = NormalizeStrength(play.StrengthCode, play.Details?.EventOwnerTeamId);

            // Determine event team
            int? eventTeamId = play.TeamId ?? play.Details?.EventOwnerTeamId;

            // Count skaters
            (int homeSkaters, int awaySkaters) = ParseSkatersFromStrength(strength, homeTeamId, awayTeamId);

            var processedEvent = new ProcessedEvent
            {
                OriginalEventIdx = i,
                GameId = gameId,
                EventIdx = i,
                Period = play.Period,
                PeriodTimeSeconds = periodTimeSeconds,
                EventType = eventType,
                EventTeamId = eventTeamId,
                X = play.XCoord ?? play.Details?.XCoord,
                Y = play.YCoord ?? play.Details?.YCoord,
                XNorm = xNorm,
                YNorm = yNorm,
                Zone = zone,
                Strength = strength,
                Description = play.Details?.Reason ?? play.TypeDescKey ?? "",
                HomeSkaters = homeSkaters,
                AwaySkaters = awaySkaters
            };

            events.Add(processedEvent);

            // Track shots
            if (eventType is "shot-on-goal" or "goal" or "missed-shot")
            {
                shots.Add(new Shot
                {
                    ShooterId = play.Details?.ShootingPlayerId ?? play.Details?.ScoringPlayerId ?? 0,
                    ShooterTeamId = eventTeamId ?? 0,
                    X = play.XCoord ?? play.Details?.XCoord,
                    Y = play.YCoord ?? play.Details?.YCoord,
                    XNorm = xNorm ?? 0,
                    YNorm = yNorm ?? 0,
                    ShotType = play.Details?.ShotType ?? "unknown",
                    IsGoal = eventType == "goal",
                    Xg = null
                });
            }

            // Track on-ice players
            if (play.Players != null)
            {
                foreach (var player in play.Players)
                {
                    eventPlayers.Add(new EventPlayer
                    {
                        PlayerId = player.PlayerId,
                        TeamId = eventTeamId ?? homeTeamId,
                        IsHome = eventTeamId == homeTeamId
                    });
                }
            }
        }

        return (events, shots, eventPlayers);
    }

    private static string NormalizeEventType(string? typeDescKey)
    {
        if (string.IsNullOrEmpty(typeDescKey)) return "unknown";

        return typeDescKey.ToLowerInvariant() switch
        {
            "faceoff" => "faceoff",
            "shot-on-goal" => "shot-on-goal",
            "goal" => "goal",
            "missed-shot" => "missed-shot",
            "blocked-shot" => "blocked-shot",
            "hit" => "hit",
            "giveaway" => "giveaway",
            "takeaway" => "takeaway",
            "penalty" => "penalty",
            "stoppage" => "stoppage",
            "period-start" => "period-start",
            "period-end" => "period-end",
            "game-end" => "game-end",
            _ => typeDescKey.ToLowerInvariant()
        };
    }

    private static string NormalizeStrength(string? strengthCode, int? eventOwnerTeamId)
    {
        if (string.IsNullOrEmpty(strengthCode)) return "EV";

        // The API sometimes returns "5v4", "5v5" etc.
        // We want to identify PK situations
        return strengthCode.ToUpperInvariant();
    }

    private static (int home, int away) ParseSkatersFromStrength(string strength, int homeTeamId, int awayTeamId)
    {
        // Parse "4v5", "3v5", etc. to extract skater counts
        // Format: "XvY" where X is home skaters, Y is away skaters
        // But API can be inconsistent — derive from context
        if (strength.Contains('v') || strength.Contains('V'))
        {
            var parts = strength.Split('v', 'V');
            if (parts.Length == 2 && int.TryParse(parts[0], out int h) && int.TryParse(parts[1], out int a))
            {
                return (h, a);
            }
        }

        // Default to 5v5
        return (5, 5);
    }

    private static int ParseTimeInPeriod(string? timeInPeriod)
    {
        if (string.IsNullOrEmpty(timeInPeriod)) return 0;

        // Format: "MM:SS"
        var parts = timeInPeriod.Split(':');
        if (parts.Length == 2 &&
            int.TryParse(parts[0], out int minutes) &&
            int.TryParse(parts[1], out int seconds))
        {
            return minutes * 60 + seconds;
        }

        return 0;
    }

    private static decimal ComputeDuration(ProcessedEvent start, ProcessedEvent end)
    {
        if (start.Period == end.Period)
        {
            return end.PeriodTimeSeconds - start.PeriodTimeSeconds;
        }
        // Across periods — rough estimate (20 min periods)
        return ((end.Period - start.Period) * 1200) + end.PeriodTimeSeconds - start.PeriodTimeSeconds;
    }

    private void AssignPossessionsToShots(List<Possession> possessions, List<Shot> shots,
        List<ProcessedEvent> events)
    {
        // This will be refined after event IDs are assigned from DB
        // For now, we'll assign during the DB write phase
    }
}