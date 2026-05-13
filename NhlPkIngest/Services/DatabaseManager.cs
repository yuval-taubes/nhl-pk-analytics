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

    public async Task DeleteGameDataAsync(NpgsqlConnection conn, NpgsqlTransaction transaction, int gameId)
    {
        var statements = new[]
        {
            "DELETE FROM shots WHERE event_id IN (SELECT event_id FROM events WHERE game_id = @gameId)",
            "DELETE FROM event_players WHERE event_id IN (SELECT event_id FROM events WHERE game_id = @gameId)",
            "DELETE FROM possessions WHERE game_id = @gameId",
            "DELETE FROM events WHERE game_id = @gameId",
            "DELETE FROM game_players WHERE game_id = @gameId"
        };

        foreach (var sql in statements)
        {
            await using var cmd = new NpgsqlCommand(sql, conn, transaction);
            cmd.Parameters.AddWithValue("gameId", gameId);
            await cmd.ExecuteNonQueryAsync();
        }
    }

    public async Task UpsertGamesAsync(NpgsqlConnection conn, NpgsqlTransaction transaction, List<Game> games)
    {
        if (games.Count == 0) return;

        await using var cmd = new NpgsqlCommand(
            @"INSERT INTO games (game_id, season, game_date, home_team_id, away_team_id, home_score, away_score)
              VALUES (@game_id, @season, @game_date, @home_team_id, @away_team_id, @home_score, @away_score)
              ON CONFLICT (game_id) DO UPDATE SET
                season = EXCLUDED.season,
                game_date = EXCLUDED.game_date,
                home_team_id = EXCLUDED.home_team_id,
                away_team_id = EXCLUDED.away_team_id,
                home_score = EXCLUDED.home_score,
                away_score = EXCLUDED.away_score",
            conn, transaction);

        cmd.Parameters.Add("@game_id", NpgsqlDbType.Integer);
        cmd.Parameters.Add("@season", NpgsqlDbType.Varchar);
        cmd.Parameters.Add("@game_date", NpgsqlDbType.Date);
        cmd.Parameters.Add("@home_team_id", NpgsqlDbType.Integer);
        cmd.Parameters.Add("@away_team_id", NpgsqlDbType.Integer);
        cmd.Parameters.Add("@home_score", NpgsqlDbType.Integer);
        cmd.Parameters.Add("@away_score", NpgsqlDbType.Integer);
        await cmd.PrepareAsync();

        foreach (var game in games)
        {
            cmd.Parameters["@game_id"].Value = game.GameId;
            cmd.Parameters["@season"].Value = (object?)game.Season ?? DBNull.Value;
            cmd.Parameters["@game_date"].Value = game.GameDate;
            cmd.Parameters["@home_team_id"].Value = game.HomeTeamId;
            cmd.Parameters["@away_team_id"].Value = game.AwayTeamId;
            cmd.Parameters["@home_score"].Value = game.HomeScore;
            cmd.Parameters["@away_score"].Value = game.AwayScore;
            await cmd.ExecuteNonQueryAsync();
        }

        _logger.LogDebug("Upserted {Count} games.", games.Count);
    }

    public async Task UpsertTeamsAsync(NpgsqlConnection conn, NpgsqlTransaction transaction, List<Team> teams)
    {
        if (teams.Count == 0) return;

        await using var cmd = new NpgsqlCommand(
            @"INSERT INTO teams (team_id, name, abbreviation)
              VALUES (@id, @name, @abbrev)
              ON CONFLICT (team_id) DO UPDATE SET
                name = EXCLUDED.name,
                abbreviation = EXCLUDED.abbreviation",
            conn, transaction);

        cmd.Parameters.Add("@id", NpgsqlDbType.Integer);
        cmd.Parameters.Add("@name", NpgsqlDbType.Varchar);
        cmd.Parameters.Add("@abbrev", NpgsqlDbType.Varchar);
        await cmd.PrepareAsync();

        foreach (var team in teams.DistinctBy(t => t.TeamId))
        {
            cmd.Parameters["@id"].Value = team.TeamId;
            cmd.Parameters["@name"].Value = team.Name;
            cmd.Parameters["@abbrev"].Value = team.Abbreviation;
            await cmd.ExecuteNonQueryAsync();
        }
    }

    public async Task UpsertPlayersAsync(NpgsqlConnection conn, NpgsqlTransaction transaction, List<Player> players)
    {
        if (players.Count == 0) return;

        await using var cmd = new NpgsqlCommand(
            @"INSERT INTO players (player_id, full_name, position)
              VALUES (@id, @name, @pos)
              ON CONFLICT (player_id) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                position = EXCLUDED.position",
            conn, transaction);

        cmd.Parameters.Add("@id", NpgsqlDbType.Integer);
        cmd.Parameters.Add("@name", NpgsqlDbType.Varchar);
        cmd.Parameters.Add("@pos", NpgsqlDbType.Varchar);
        await cmd.PrepareAsync();

        foreach (var player in players.DistinctBy(p => p.PlayerId))
        {
            cmd.Parameters["@id"].Value = player.PlayerId;
            cmd.Parameters["@name"].Value = player.FullName;
            cmd.Parameters["@pos"].Value = player.Position;
            await cmd.ExecuteNonQueryAsync();
        }
    }

    public async Task UpsertGamePlayersAsync(NpgsqlConnection conn, NpgsqlTransaction transaction, List<GamePlayer> gamePlayers)
    {
        if (gamePlayers.Count == 0) return;

        await using var cmd = new NpgsqlCommand(
            @"INSERT INTO game_players (game_id, player_id, team_id)
              VALUES (@game_id, @player_id, @team_id)
              ON CONFLICT (game_id, player_id) DO UPDATE SET
                team_id = EXCLUDED.team_id",
            conn, transaction);

        cmd.Parameters.Add("@game_id", NpgsqlDbType.Integer);
        cmd.Parameters.Add("@player_id", NpgsqlDbType.Integer);
        cmd.Parameters.Add("@team_id", NpgsqlDbType.Integer);
        await cmd.PrepareAsync();

        foreach (var gp in gamePlayers.DistinctBy(gp => (gp.GameId, gp.PlayerId)))
        {
            cmd.Parameters["@game_id"].Value = gp.GameId;
            cmd.Parameters["@player_id"].Value = gp.PlayerId;
            cmd.Parameters["@team_id"].Value = gp.TeamId;
            await cmd.ExecuteNonQueryAsync();
        }
    }

    public async Task InsertEventsAsync(NpgsqlConnection conn, List<Event> events)
    {
        if (events.Count == 0) return;

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
        _logger.LogDebug("Inserted {Count} events.", events.Count);
    }

    public async Task<int[]> GetEventIdsBatchAsync(NpgsqlConnection conn, NpgsqlTransaction transaction, int gameId, int count)
    {
        await using var cmd = new NpgsqlCommand(
            @"SELECT event_id
              FROM events
              WHERE game_id = @gameId
              ORDER BY event_idx",
            conn, transaction);
        cmd.Parameters.AddWithValue("gameId", gameId);

        var ids = new List<int>();
        await using var reader = await cmd.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            ids.Add(reader.GetInt32(0));
        }

        if (ids.Count != count)
        {
            throw new InvalidOperationException($"Expected {count} event IDs for game {gameId}, found {ids.Count}.");
        }

        return ids.ToArray();
    }

    public async Task InsertPossessionsAsync(NpgsqlConnection conn, NpgsqlTransaction transaction, List<Possession> possessions)
    {
        if (possessions.Count == 0) return;

        await using var cmd = new NpgsqlCommand(
            @"INSERT INTO possessions (game_id, team_id, start_event_id, end_event_id, strength,
                entry_type, entry_x, entry_y, start_zone, end_type, duration_seconds,
                shot_count, goal_count, xg_sum)
              VALUES (@game_id, @team_id, @start_event_id, @end_event_id, @strength,
                @entry_type, @entry_x, @entry_y, @start_zone, @end_type, @duration_seconds,
                @shot_count, @goal_count, @xg_sum)
              RETURNING possession_id",
            conn, transaction);

        cmd.Parameters.Add("@game_id", NpgsqlDbType.Integer);
        cmd.Parameters.Add("@team_id", NpgsqlDbType.Integer);
        cmd.Parameters.Add("@start_event_id", NpgsqlDbType.Integer);
        cmd.Parameters.Add("@end_event_id", NpgsqlDbType.Integer);
        cmd.Parameters.Add("@strength", NpgsqlDbType.Varchar);
        cmd.Parameters.Add("@entry_type", NpgsqlDbType.Varchar);
        cmd.Parameters.Add("@entry_x", NpgsqlDbType.Integer);
        cmd.Parameters.Add("@entry_y", NpgsqlDbType.Integer);
        cmd.Parameters.Add("@start_zone", NpgsqlDbType.Varchar);
        cmd.Parameters.Add("@end_type", NpgsqlDbType.Varchar);
        cmd.Parameters.Add("@duration_seconds", NpgsqlDbType.Numeric);
        cmd.Parameters.Add("@shot_count", NpgsqlDbType.Integer);
        cmd.Parameters.Add("@goal_count", NpgsqlDbType.Integer);
        cmd.Parameters.Add("@xg_sum", NpgsqlDbType.Numeric);
        await cmd.PrepareAsync();

        foreach (var poss in possessions)
        {
            cmd.Parameters["@game_id"].Value = poss.GameId;
            cmd.Parameters["@team_id"].Value = poss.TeamId;
            cmd.Parameters["@start_event_id"].Value = poss.StartEventId;
            cmd.Parameters["@end_event_id"].Value = poss.EndEventId;
            cmd.Parameters["@strength"].Value = (object?)poss.Strength ?? DBNull.Value;
            cmd.Parameters["@entry_type"].Value = (object?)poss.EntryType ?? DBNull.Value;
            cmd.Parameters["@entry_x"].Value = (object?)poss.EntryX ?? DBNull.Value;
            cmd.Parameters["@entry_y"].Value = (object?)poss.EntryY ?? DBNull.Value;
            cmd.Parameters["@start_zone"].Value = (object?)poss.StartZone ?? DBNull.Value;
            cmd.Parameters["@end_type"].Value = (object?)poss.EndType ?? DBNull.Value;
            cmd.Parameters["@duration_seconds"].Value = poss.DurationSeconds;
            cmd.Parameters["@shot_count"].Value = poss.ShotCount;
            cmd.Parameters["@goal_count"].Value = poss.GoalCount;
            cmd.Parameters["@xg_sum"].Value = poss.XgSum;
            poss.PossessionId = (int)(await cmd.ExecuteScalarAsync() ?? 0);
        }

        _logger.LogDebug("Inserted {Count} possessions.", possessions.Count);
    }

    public async Task InsertShotsAsync(NpgsqlConnection conn, List<Shot> shots)
    {
        if (shots.Count == 0) return;

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
        _logger.LogDebug("Inserted {Count} shots.", shots.Count);
    }

    public async Task InsertEventPlayersAsync(NpgsqlConnection conn, List<EventPlayer> eventPlayers)
    {
        if (eventPlayers.Count == 0) return;

        var distinct = eventPlayers
            .GroupBy(ep => (ep.EventId, ep.PlayerId))
            .Select(g => g.First())
            .ToList();

        await using var writer = await conn.BeginBinaryImportAsync(
            "COPY event_players (event_id, player_id, team_id, is_home, original_event_idx) FROM STDIN (FORMAT BINARY)");

        foreach (var ep in distinct)
        {
            await writer.StartRowAsync();
            await writer.WriteAsync(ep.EventId, NpgsqlDbType.Integer);
            await writer.WriteAsync(ep.PlayerId, NpgsqlDbType.Integer);
            await writer.WriteAsync(ep.TeamId, NpgsqlDbType.Integer);
            await writer.WriteAsync(ep.IsHome, NpgsqlDbType.Boolean);
            await writer.WriteAsync(ep.OriginalEventIdx, NpgsqlDbType.Integer);
        }

        await writer.CompleteAsync();
        _logger.LogDebug("Inserted {Count} event_players (deduped from {Original})", distinct.Count, eventPlayers.Count);
    }
}
