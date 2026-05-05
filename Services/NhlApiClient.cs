using System.Net.Http.Json;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Configuration;
using NhlPkIngest.Models;

namespace NhlPkIngest.Services;

public class NhlApiClient
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<NhlApiClient> _logger;
    private readonly int _maxRetries;
    private readonly int _delayMs;

    public NhlApiClient(HttpClient httpClient, IConfiguration config, ILogger<NhlApiClient> logger)
    {
        _httpClient = httpClient;
        _logger = logger;
        _maxRetries = config.GetValue<int>("NhlApi:MaxRetries", 5);
        _delayMs = config.GetValue<int>("NhlApi:DelayMs", 500);
        _httpClient.Timeout = TimeSpan.FromSeconds(30);
    }

    public async Task<NhlPlayByPlayResponse?> GetPlayByPlayAsync(int gameId)
    {
        var url = $"https://api.nhle.com/stats/rest/en/game/{gameId}/play-by-play";

        for (int attempt = 1; attempt <= _maxRetries; attempt++)
        {
            try
            {
                _logger.LogDebug("Fetching game {GameId}, attempt {Attempt}", gameId, attempt);
                var response = await _httpClient.GetAsync(url);

                if (response.StatusCode == System.Net.HttpStatusCode.NotFound)
                {
                    _logger.LogDebug("Game {GameId} not found (404). Skipping.", gameId);
                    return null;
                }

                if (response.StatusCode == System.Net.HttpStatusCode.Forbidden)
                {
                    _logger.LogDebug("Game {GameId} forbidden (403). Skipping.", gameId);
                    return null;
                }

                response.EnsureSuccessStatusCode();

                var pbp = await response.Content.ReadFromJsonAsync<NhlPlayByPlayResponse>();
                if (pbp == null || pbp.Plays == null || pbp.Plays.Count == 0)
                {
                    _logger.LogWarning("Game {GameId} returned empty play-by-play data.", gameId);
                    return null;
                }

                return pbp;
            }
            catch (HttpRequestException ex) when (ex.StatusCode != System.Net.HttpStatusCode.NotFound)
            {
                _logger.LogWarning(ex, "Attempt {Attempt} failed for game {GameId}: {Message}", attempt, gameId, ex.Message);
                if (attempt == _maxRetries)
                {
                    _logger.LogError("All {MaxRetries} attempts failed for game {GameId}.", _maxRetries, gameId);
                    throw;
                }
                await Task.Delay(_delayMs * attempt);
            }
            catch (TaskCanceledException)
            {
                _logger.LogWarning("Timeout for game {GameId}, attempt {Attempt}", gameId, attempt);
                if (attempt == _maxRetries) throw;
                await Task.Delay(_delayMs * attempt);
            }
        }

        return null;
    }

    public async Task<List<int>> GetGameIdsForSeasonAsync(string season)
    {
        var gameIds = new HashSet<int>();
        
        int seasonStartYear = int.Parse(season.Substring(0, 4));
        int seasonEndYear = int.Parse(season.Substring(4, 4));
        
        var startDate = new DateOnly(seasonStartYear, 10, 1);
        var endDate = new DateOnly(seasonEndYear, 4, 30);
        
        _logger.LogInformation("Fetching schedules from {Start} to {End} for season {Season}",
            startDate, endDate, season);
        
        int totalDays = 0;
        int daysWithGames = 0;
        
        for (var date = startDate; date <= endDate; date = date.AddDays(1))
        {
            totalDays++;
            var url = $"https://api-web.nhle.com/v1/schedule/{date:yyyy-MM-dd}";
            
            try
            {
                var response = await _httpClient.GetAsync(url);
                
                if (response.StatusCode == System.Net.HttpStatusCode.NotFound)
                {
                    continue;
                }
                
                response.EnsureSuccessStatusCode();
                var json = await response.Content.ReadAsStringAsync();
                
                using var doc = System.Text.Json.JsonDocument.Parse(json);
                
                // The schedule endpoint can return multiple days in gameWeek array
                if (doc.RootElement.TryGetProperty("gameWeek", out var gameWeek))
                {
                    foreach (var day in gameWeek.EnumerateArray())
                    {
                        if (!day.TryGetProperty("games", out var games))
                            continue;
                        
                        foreach (var game in games.EnumerateArray())
                        {
                            if (!game.TryGetProperty("id", out var idElement))
                                continue;
                            
                            int gameId = idElement.GetInt32();
                            
                            // Only include games for the target season
                            if (game.TryGetProperty("season", out var seasonElement))
                            {
                                if (seasonElement.GetInt32().ToString() == season)
                                {
                                    gameIds.Add(gameId);
                                }
                            }
                        }
                        
                        if (games.GetArrayLength() > 0)
                        {
                            daysWithGames++;
                        }
                    }
                }
                
                await Task.Delay(100);
            }
            catch (HttpRequestException ex)
            {
                _logger.LogWarning(ex, "Failed to fetch schedule for {Date}", date);
            }
        }
        
        _logger.LogInformation("Found {Count} unique game IDs across {DaysWithGames}/{TotalDays} days for season {Season}",
            gameIds.Count, daysWithGames, totalDays, season);
        
        return gameIds.ToList();
    }
}