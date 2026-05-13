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
    private readonly PossessionTracker _possessionTracker;
    private readonly ILogger<GameIngester> _logger;

    public GameIngester(
        NhlApiClient apiClient,
        DatabaseManager dbManager,
        PossessionTracker possessionTracker,
        ILogger<GameIngester> logger)
    {
        _apiClient = apiClient;
        _dbManager = dbManager;
        _possessionTracker = possessionTracker;
        _logger = logger;
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
            new Team { TeamId = homeTeamId, Name = pbp.HomeTeam.Name, Abbreviation = pbp.HomeTeam.Abbrev! },
            new Team { TeamId = awayTeamId, Name = pbp.AwayTeam.Name, Abbreviation = pbp.AwayTeam.Abbrev! }
        };

        // 2. Process game metadata
        var game = new Game
        {
            GameId = gameId,
            Season = pbp.Season.ToString(),
            GameDate = DateOnly.TryParse(pbp.GameDate, out var d) ? d : DateOnly.MinValue,
            HomeTeamId = homeTeamId,
            AwayTeamId = awayTeamId,
            HomeScore = pbp.HomeTeam.Score,
            AwayScore = pbp.AwayTeam.Score
        };

        // 3. Process players from rosters
        var players = new List<Player>();
        var gamePlayers = new List<GamePlayer>();

if (pbp.RosterSpots != null)
{
    foreach (var p in pbp.RosterSpots)
    {
        players.Add(new Player { PlayerId = p.PlayerId, FullName = p.FullName, Position = p.PositionCode ?? "NA" });
        gamePlayers.Add(new GamePlayer { GameId = gameId, PlayerId = p.PlayerId, TeamId = p.TeamId });
    }
}
        // 4. Process events
        var (processedEvents, shots, eventPlayers) = ProcessEvents(
            pbp.Plays!, gameId, homeTeamId, awayTeamId);

        // 5. Derive possessions for PK strengths
        var allPossessions = new List<Possession>();
        foreach (var strength in new[] { "4v5", "3v5", "3v4", "5v5", "5v4", "5v3", "4v4", "3v3" })
        {
            var possessions = _possessionTracker.ExtractPossessions(
                processedEvents, gameId, homeTeamId, strength);
            allPossessions.AddRange(possessions);
        }

        // 6. Bulk insert everything
        await using var conn = _dbManager.CreateConnection();
        await using var transaction = await conn.BeginTransactionAsync();

        try
        {
            // Insert reference data first, then clear and replace all game-scoped rows.
            await _dbManager.UpsertTeamsAsync(conn, transaction, teams.DistinctBy(t => t.TeamId).ToList());
            await _dbManager.UpsertPlayersAsync(conn, transaction, players.DistinctBy(p => p.PlayerId).ToList());
            await _dbManager.DeleteGameDataAsync(conn, transaction, gameId);
            await _dbManager.UpsertGamesAsync(conn, transaction, new List<Game> { game });
            await _dbManager.UpsertGamePlayersAsync(conn, transaction, gamePlayers);

            // Events must be inserted before possessions (need event_ids)
            await _dbManager.InsertEventsAsync(conn, processedEvents.Select(e => e.ToEvent()).ToList());

            // Now get the actual event IDs (SERIAL from DB)
            var eventIds = await _dbManager.GetEventIdsBatchAsync(conn, transaction, gameId, processedEvents.Count);
            for (int i = 0; i < processedEvents.Count; i++)
            {
                processedEvents[i].EventId = eventIds[i];
            }

            // Update possessions with real event IDs
            foreach (var poss in allPossessions)
            {
                var startPe = processedEvents.FirstOrDefault(e => e.OriginalEventIdx == poss.StartEventOriginalIdx);
                var endPe = processedEvents.FirstOrDefault(e => e.OriginalEventIdx == poss.EndEventOriginalIdx);
                
                if (startPe != null)
                    poss.StartEventId = startPe.EventId;
                if (endPe != null)
                    poss.EndEventId = endPe.EventId;
                
                if (startPe != null && endPe != null)
                    poss.DurationSeconds = ComputeDuration(startPe, endPe);
            }

            await _dbManager.InsertPossessionsAsync(conn, transaction, allPossessions);

            // Update shot possession IDs and event IDs
            foreach (var shot in shots)
            {
            var pe = processedEvents.FirstOrDefault(e => e.OriginalEventIdx == shot.OriginalEventIdx);
            if (pe != null) shot.EventId = pe.EventId;

                var containingPossession = allPossessions
                    .FirstOrDefault(p => shot.EventId >= p.StartEventId &&
                                         shot.EventId <= p.EndEventId &&
                                         p.TeamId == shot.ShooterTeamId);
                if (containingPossession != null)
                {
                    shot.PossessionId = containingPossession.PossessionId;
                }
            }

            await _dbManager.InsertShotsAsync(conn, shots);

            // Backfill event_id on eventPlayers
foreach (var ep in eventPlayers)
{
    var pe = processedEvents.FirstOrDefault(e => e.OriginalEventIdx == ep.OriginalEventIdx);
    if (pe != null) ep.EventId = pe.EventId;
}

            await _dbManager.InsertEventPlayersAsync(conn, eventPlayers);

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
        int apiZoneCount = 0;
        int derivedZoneCount = 0;
        int fallbackZoneCount = 0;
        int missingZoneCount = 0;


        for (int i = 0; i < plays.Count; i++)
        {
            var play = plays[i];
            var eventType = NormalizeEventType(play.TypeDescKey);
            var period = play.Period;
            var periodTimeSeconds = ParseTimeInPeriod(play.TimeInPeriod);
            var strength = play.StrengthCode;
            var eventTeamId = play.TeamId;

            // Normalize coordinates
            bool isHomeEvent = eventTeamId == homeTeamId;
            CoordinateNormalizer.Normalize(
                play.XCoord, play.YCoord,
                period, isHomeEvent,
                out int? xNorm, out int? yNorm);

            // Determine zone from coordinates if not provided
            string zone = play.ZoneCode;
            if (string.IsNullOrEmpty(zone) && xNorm != null)
            {
                zone = CoordinateNormalizer.DetermineZone(xNorm, eventTeamId, homeTeamId);
            }

            // Normalize zone codes: NHL API sometimes returns "O"/"D"/"N" instead of "OZ"/"DZ"/"NZ"
            zone = zone?.ToUpperInvariant() switch
            {
                "O" => "OZ",
                "D" => "DZ",
                "N" => "NZ",
                _ => zone ?? "NZ"
            };

            // If zone is still empty after API + coordinate determination, use x_norm alone
            if (string.IsNullOrEmpty(zone) && xNorm != null)
            {
                zone = CoordinateNormalizer.DetermineZoneFromX(xNorm);
            }
            else if (string.IsNullOrEmpty(zone))
            {
                zone = "NZ"; // last resort default
            }

            if (!string.IsNullOrEmpty(play.ZoneCode))
                apiZoneCount++;
            else if (xNorm != null && !string.IsNullOrEmpty(zone))
                derivedZoneCount++;
            else if (!string.IsNullOrEmpty(zone))
                fallbackZoneCount++;
            else
                missingZoneCount++;

            // Parse skater counts from situation code
            (int homeSkaters, int awaySkaters) = ParseSkatersFromSituationCode(play.SituationCode);

            var processedEvent = new ProcessedEvent
            {
                OriginalEventIdx = i,
                GameId = gameId,
                EventIdx = i,
                Period = period,
                PeriodTimeSeconds = periodTimeSeconds,
                EventType = eventType,
                EventTeamId = eventTeamId,
                X = play.XCoord,
                Y = play.YCoord,
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
if (eventType is "shot-on-goal" or "goal" or "missed-shot" or "blocked-shot")
{
    int shooterId = play.Details?.ShootingPlayerId
                 ?? play.Details?.ScoringPlayerId
                 ?? play.Details?.PlayerId ?? 0;
    
    if (shooterId == 0)
    {
        _logger.LogDebug("Skipping shot at event {Idx}: no shooter ID available", i);
    }
    else
    {
        shots.Add(new Shot
        {
            OriginalEventIdx = i,
            ShooterId = shooterId,
            ShooterTeamId = eventTeamId ?? 0,
            X = play.XCoord,
            Y = play.YCoord,
            XNorm = xNorm ?? 0,
            YNorm = yNorm ?? 0,
            ShotType = play.Details?.ShotType ?? "unknown",
            IsGoal = eventType == "goal",
            Xg = null
        });
    }
}

            // Track on-ice players
            if (play.Details != null)
            {
                AddPlayerIfNotNull(eventPlayers, play.Details.WinningPlayerId, eventTeamId, homeTeamId, i);
                AddPlayerIfNotNull(eventPlayers, play.Details.LosingPlayerId, eventTeamId, homeTeamId, i);
                AddPlayerIfNotNull(eventPlayers, play.Details.ScoringPlayerId, eventTeamId, homeTeamId, i);
                AddPlayerIfNotNull(eventPlayers, play.Details.ShootingPlayerId, eventTeamId, homeTeamId, i);
                AddPlayerIfNotNull(eventPlayers, play.Details.GoalieInNetId, eventTeamId, homeTeamId, i);
                AddPlayerIfNotNull(eventPlayers, play.Details.HittingPlayerId, eventTeamId, homeTeamId, i);
                AddPlayerIfNotNull(eventPlayers, play.Details.HitteePlayerId, eventTeamId, homeTeamId, i);
                AddPlayerIfNotNull(eventPlayers, play.Details.CommittedByPlayerId, eventTeamId, homeTeamId, i);
                AddPlayerIfNotNull(eventPlayers, play.Details.DrawnByPlayerId, eventTeamId, homeTeamId, i);
                AddPlayerIfNotNull(eventPlayers, play.Details.BlockingPlayerId, eventTeamId, homeTeamId, i);
                AddPlayerIfNotNull(eventPlayers, play.Details.PlayerId, eventTeamId, homeTeamId, i);
                AddPlayerIfNotNull(eventPlayers, play.Details.Assist1PlayerId, eventTeamId, homeTeamId, i);
                AddPlayerIfNotNull(eventPlayers, play.Details.Assist2PlayerId, eventTeamId, homeTeamId, i);
            }
        }
        _logger.LogInformation("Game {GameId} zones: API={Api}, Derived={Derived}, Fallback={Fallback}, Missing={Missing}",
        gameId, apiZoneCount, derivedZoneCount, fallbackZoneCount, missingZoneCount);
        return (events, shots, eventPlayers);
    }

   private static void AddPlayerIfNotNull(List<EventPlayer> list, int? playerId,
       int? eventTeamId, int homeTeamId, int originalEventIdx)  // ADD param
   {
       if (playerId == null) return;
       list.Add(new EventPlayer
       {
           PlayerId = playerId.Value,
           TeamId = eventTeamId ?? 0,
           IsHome = eventTeamId == homeTeamId,
           OriginalEventIdx = originalEventIdx  // SET IT
       });
   }
    private static (int home, int away) ParseSkatersFromSituationCode(string? situationCode)
    {
        if (string.IsNullOrEmpty(situationCode) || situationCode.Length < 4)
            return (5, 5);

        if (int.TryParse(situationCode.Substring(1, 1), out int away) &&
            int.TryParse(situationCode.Substring(2, 1), out int home))
        {
            return (home, away);
        }
        return (5, 5);
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
            "delayed-penalty" => "delayed-penalty",
            _ => typeDescKey.ToLowerInvariant()
        };
    }

    private static int ParseTimeInPeriod(string? timeInPeriod)
    {
        if (string.IsNullOrEmpty(timeInPeriod)) return 0;

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
        return ((end.Period - start.Period) * 1200) + end.PeriodTimeSeconds - start.PeriodTimeSeconds;
    }
}
