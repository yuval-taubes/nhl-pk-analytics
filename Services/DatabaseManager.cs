using System.Data;
using Npgsql;
using NpgsqlTypes;
using Microsoft.Extensions.Logging;
using NhlPkIngest.Models;
namespace NhlPkIngest.Services;

public class DatabaseManager
{
    private readonly string _connectionString;
    private readonly ILogger<DatabaseManager> _logger;

    public DatabaseManager(string connectionString, ILogger<DatabaseManager> logger)
    {
        _connectionString = connectionString;
        _logger = logger;
    }

    public NpgsqlConnection CreateConnection()
    {
        var conn = new NpgsqlConnection(_connectionString);
        conn.Open();
        return conn;
    }

    public async Task InitializeSchemaAsync()
    {
        _logger.LogInformation("Initializing database schema...");
        var ddl = await File.ReadAllTextAsync("schema.sql");
        await using var conn = CreateConnection();
        await using var cmd = new NpgsqlCommand(ddl, conn);
        await cmd.ExecuteNonQueryAsync();
        _logger.LogInformation("Schema initialization complete.");
    }

    public async Task<HashSet<int>> GetExistingGameIdsAsync()
    {
        var gameIds = new HashSet<int>();
        await using var conn = CreateConnection();
        await using var cmd = new NpgsqlCommand("SELECT game_id FROM games", conn);
        await using var reader = await cmd.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            gameIds.Add(reader.GetInt32(0));
        }
        _logger.LogInformation("Found {Count} existing games in database.", gameIds.Count);
        return gameIds;
    }

    public async Task BulkCopyGamesAsync(List<Game> games)
    {
        if (games.Count == 0) return;

        await using var conn = CreateConnection();
        await using var writer = await conn.BeginBinaryImportAsync(
            "COPY games (game_id, season, game_date, home_team_id, away_team_id, home_score, away_score) FROM STDIN (FORMAT BINARY)");

        foreach (var game in games)
        {
            await writer.StartRowAsync();
            await writer.WriteAsync(game.GameId, NpgsqlDbType.Integer);
            await writer.WriteAsync(game.Season, NpgsqlDbType.Varchar);
            await writer.WriteAsync(game.GameDate, NpgsqlDbType.Date);
            await writer.WriteAsync(game.HomeTeamId, NpgsqlDbType.Integer);
            await writer.WriteAsync(game.AwayTeamId, NpgsqlDbType.Integer);
            await writer.WriteAsync(game.HomeScore, NpgsqlDbType.Integer);
            await writer.WriteAsync(game.AwayScore, NpgsqlDbType.Integer);
        }

        await writer.CompleteAsync();
        _logger.LogDebug("Bulk copied {Count} games.", games.Count);
    }

    public async Task BulkCopyTeamsAsync(List<Team> teams)
{
    if (teams.Count == 0) return;

    await using var conn = CreateConnection();
    await using var cmd = new NpgsqlCommand(
        @"INSERT INTO teams (team_id, name, abbreviation) 
          VALUES (@id, @name, @abbrev) 
          ON CONFLICT (team_id) DO NOTHING", conn);
    
    cmd.Parameters.Add("@id", NpgsqlTypes.NpgsqlDbType.Integer);
    cmd.Parameters.Add("@name", NpgsqlTypes.NpgsqlDbType.Varchar);
    cmd.Parameters.Add("@abbrev", NpgsqlTypes.NpgsqlDbType.Varchar);
    await cmd.PrepareAsync();

    foreach (var team in teams.DistinctBy(t => t.TeamId))
    {
        cmd.Parameters["@id"].Value = team.TeamId;
        cmd.Parameters["@name"].Value = team.Name;
        cmd.Parameters["@abbrev"].Value = team.Abbreviation;
        await cmd.ExecuteNonQueryAsync();
    }
}
    public async Task BulkCopyPlayersAsync(List<Player> players)
{
    if (players.Count == 0) return;

    var distinct = players.DistinctBy(p => p.PlayerId).ToList();
    
    await using var conn = CreateConnection();
    await using var cmd = new NpgsqlCommand(
        @"INSERT INTO players (player_id, full_name, position) 
          VALUES (@id, @name, @pos) 
          ON CONFLICT (player_id) DO NOTHING", conn);
    
    cmd.Parameters.Add("@id", NpgsqlTypes.NpgsqlDbType.Integer);
    cmd.Parameters.Add("@name", NpgsqlTypes.NpgsqlDbType.Varchar);
    cmd.Parameters.Add("@pos", NpgsqlTypes.NpgsqlDbType.Varchar);
    await cmd.PrepareAsync();

    foreach (var player in distinct)
    {
        cmd.Parameters["@id"].Value = player.PlayerId;
        cmd.Parameters["@name"].Value = player.FullName;
        cmd.Parameters["@pos"].Value = player.Position;
        await cmd.ExecuteNonQueryAsync();
    }
}
    public async Task BulkCopyGamePlayersAsync(List<GamePlayer> gamePlayers)
    {
        if (gamePlayers.Count == 0) return;

        await using var conn = CreateConnection();
        await using var writer = await conn.BeginBinaryImportAsync(
            "COPY game_players (game_id, player_id, team_id) FROM STDIN (FORMAT BINARY)");

        foreach (var gp in gamePlayers)
        {
            await writer.StartRowAsync();
            await writer.WriteAsync(gp.GameId, NpgsqlDbType.Integer);
            await writer.WriteAsync(gp.PlayerId, NpgsqlDbType.Integer);
            await writer.WriteAsync(gp.TeamId, NpgsqlDbType.Integer);
        }

        await writer.CompleteAsync();
        _logger.LogDebug("Bulk copied {Count} game_players.", gamePlayers.Count);
    }

    public async Task BulkCopyEventsAsync(List<Event> events)
    {
        if (events.Count == 0) return;

        await using var conn = CreateConnection();
        await using var writer = await conn.BeginBinaryImportAsync(
            @"COPY events (game_id, event_idx, period, period_time_seconds, event_type, 
               event_team_id, x, y, x_norm, y_norm, zone, strength, description, 
               home_skaters, away_skaters) 
               FROM STDIN (FORMAT BINARY)");

        foreach (var evt in events)
        {
            await writer.StartRowAsync();
            await writer.WriteAsync(evt.GameId, NpgsqlDbType.Integer);
            await writer.WriteAsync(evt.EventIdx, NpgsqlDbType.Integer);
            await writer.WriteAsync(evt.Period, NpgsqlDbType.Integer);
            await writer.WriteAsync(evt.PeriodTimeSeconds, NpgsqlDbType.Integer);
            await writer.WriteAsync(evt.EventType, NpgsqlDbType.Varchar);
            await writer.WriteAsync(evt.EventTeamId, NpgsqlDbType.Integer);
            await writer.WriteAsync(evt.X, NpgsqlDbType.Integer);
            await writer.WriteAsync(evt.Y, NpgsqlDbType.Integer);
            await writer.WriteAsync(evt.XNorm, NpgsqlDbType.Integer);
            await writer.WriteAsync(evt.YNorm, NpgsqlDbType.Integer);
            await writer.WriteAsync(evt.Zone, NpgsqlDbType.Varchar);
            await writer.WriteAsync(evt.Strength, NpgsqlDbType.Varchar);
            await writer.WriteAsync(evt.Description, NpgsqlDbType.Text);
            await writer.WriteAsync(evt.HomeSkaters, NpgsqlDbType.Integer);
            await writer.WriteAsync(evt.AwaySkaters, NpgsqlDbType.Integer);
        }

        await writer.CompleteAsync();
        _logger.LogDebug("Bulk copied {Count} events.", events.Count);
    }

    public async Task<int[]> GetEventIdsBatchAsync(int gameId, int count)
    {
        // After inserting events, we need their generated event_ids for possessions/shots
        await using var conn = CreateConnection();
        await using var cmd = new NpgsqlCommand(
            @"SELECT event_id FROM events 
              WHERE game_id = @gameId 
              ORDER BY event_idx 
              OFFSET (SELECT COUNT(*) FROM events WHERE game_id = @gameId) - @count",
            conn);
        cmd.Parameters.AddWithValue("gameId", gameId);
        cmd.Parameters.AddWithValue("count", count);
        var ids = new List<int>();
        await using var reader = await cmd.ExecuteReaderAsync();
        while (await reader.ReadAsync())
            ids.Add(reader.GetInt32(0));
        return ids.ToArray();
    }

    public async Task BulkCopyShotsAsync(List<Shot> shots)
    {
        if (shots.Count == 0) return;

        await using var conn = CreateConnection();
        await using var writer = await conn.BeginBinaryImportAsync(
            @"COPY shots (event_id, possession_id, shooter_id, x, y, x_norm, y_norm, shot_type, is_goal, xg) 
              FROM STDIN (FORMAT BINARY)");

foreach (var shot in shots)
{
    await writer.StartRowAsync();
    await writer.WriteAsync(shot.EventId, NpgsqlDbType.Integer);
    await writer.WriteAsync(shot.PossessionId == 0 ? DBNull.Value : (object)shot.PossessionId, NpgsqlDbType.Integer);
    await writer.WriteAsync(shot.ShooterId == 0 ? DBNull.Value : (object)shot.ShooterId, NpgsqlDbType.Integer);
    await writer.WriteAsync(shot.X, NpgsqlDbType.Integer);
    await writer.WriteAsync(shot.Y, NpgsqlDbType.Integer);
    await writer.WriteAsync(shot.XNorm, NpgsqlDbType.Integer);
    await writer.WriteAsync(shot.YNorm, NpgsqlDbType.Integer);
    await writer.WriteAsync(shot.ShotType, NpgsqlDbType.Varchar);
    await writer.WriteAsync(shot.IsGoal, NpgsqlDbType.Boolean);
    await writer.WriteAsync(shot.Xg, NpgsqlDbType.Numeric);
}
        await writer.CompleteAsync();
        _logger.LogDebug("Bulk copied {Count} shots.", shots.Count);
    }

    public async Task BulkCopyPossessionsAsync(List<Possession> possessions)
    {
        if (possessions.Count == 0) return;

        await using var conn = CreateConnection();
        await using var writer = await conn.BeginBinaryImportAsync(
            @"COPY possessions (game_id, team_id, start_event_id, end_event_id, strength,
              entry_type, entry_x, entry_y, start_zone, end_type, duration_seconds,
              shot_count, goal_count, xg_sum)
              FROM STDIN (FORMAT BINARY)");

        foreach (var poss in possessions)
        {
            await writer.StartRowAsync();
            await writer.WriteAsync(poss.GameId, NpgsqlDbType.Integer);
            await writer.WriteAsync(poss.TeamId, NpgsqlDbType.Integer);
            await writer.WriteAsync(poss.StartEventId, NpgsqlDbType.Integer);
            await writer.WriteAsync(poss.EndEventId, NpgsqlDbType.Integer);
            await writer.WriteAsync(poss.Strength, NpgsqlDbType.Varchar);
            await writer.WriteAsync(poss.EntryType, NpgsqlDbType.Varchar);
            await writer.WriteAsync(poss.EntryX, NpgsqlDbType.Integer);
            await writer.WriteAsync(poss.EntryY, NpgsqlDbType.Integer);
            await writer.WriteAsync(poss.StartZone, NpgsqlDbType.Varchar);
            await writer.WriteAsync(poss.EndType, NpgsqlDbType.Varchar);
            await writer.WriteAsync(poss.DurationSeconds, NpgsqlDbType.Numeric);
            await writer.WriteAsync(poss.ShotCount, NpgsqlDbType.Integer);
            await writer.WriteAsync(poss.GoalCount, NpgsqlDbType.Integer);
            await writer.WriteAsync(poss.XgSum, NpgsqlDbType.Numeric);
        }

        await writer.CompleteAsync();
        _logger.LogDebug("Bulk copied {Count} possessions.", possessions.Count);
    }

    public async Task BulkCopyEventPlayersAsync(List<EventPlayer> eventPlayers)
{
    if (eventPlayers.Count == 0) return;

    // Deduplicate by (event_id, player_id)
   var distinct = eventPlayers
       .GroupBy(ep => (ep.OriginalEventIdx, ep.PlayerId))
       .Select(g => g.First())
       .ToList();

    await using var conn = CreateConnection();
    await using var writer = await conn.BeginBinaryImportAsync(
        "COPY event_players (event_id, player_id, team_id, is_home) FROM STDIN (FORMAT BINARY)");

    foreach (var ep in distinct)
    {
        await writer.StartRowAsync();
        await writer.WriteAsync(ep.EventId, NpgsqlDbType.Integer);
        await writer.WriteAsync(ep.PlayerId, NpgsqlDbType.Integer);
        await writer.WriteAsync(ep.TeamId, NpgsqlDbType.Integer);
        await writer.WriteAsync(ep.IsHome, NpgsqlDbType.Boolean);
    }

    await writer.CompleteAsync();
    _logger.LogDebug("Bulk copied {Count} event_players (deduped from {Original})", distinct.Count, eventPlayers.Count);
}

    /// <summary>
    /// Upserts events to handle game re-processing (uses temp table + MERGE pattern).
    /// </summary>
    public async Task UpsertEventsForGameAsync(int gameId, List<Event> events)
    {
        if (events.Count == 0) return;

        await using var conn = CreateConnection();
        // Delete existing events for this game first (cascades to event_players, shots)
        await using var deleteCmd = new NpgsqlCommand(
            "DELETE FROM events WHERE game_id = @gameId", conn);
        deleteCmd.Parameters.AddWithValue("gameId", gameId);
        await deleteCmd.ExecuteNonQueryAsync();

        // Then bulk insert the new ones
        await BulkCopyEventsAsync(events);
    }
}