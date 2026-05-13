using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using NhlPkIngest.Services;

namespace NhlPkIngest;

class Program
{
    static async Task Main(string[] args)
    {
        var configuration = new ConfigurationBuilder()
            .SetBasePath(Directory.GetCurrentDirectory())
            .AddJsonFile("appsettings.json", optional: false)
            .AddEnvironmentVariables()
            .AddCommandLine(args)
            .Build();

        var services = new ServiceCollection();
        ConfigureServices(services, configuration);
        var serviceProvider = services.BuildServiceProvider();

        var logger = serviceProvider.GetRequiredService<ILogger<Program>>();
        logger.LogInformation("NHL PK Analytics Ingest starting...");

        try
        {
            var dbManager = serviceProvider.GetRequiredService<DatabaseManager>();
            var apiClient = serviceProvider.GetRequiredService<NhlApiClient>();
            var gameIngester = serviceProvider.GetRequiredService<GameIngester>();

            await dbManager.InitializeSchemaAsync();

            var existingGameIds = await dbManager.GetExistingGameIdsAsync();

            // TEMP: Single season for testing
            var seasons = configuration.GetSection("Seasons").Get<string[]>() ?? Array.Empty<string>();
            logger.LogInformation("Processing {Count} seasons: {Seasons}", seasons.Length, string.Join(", ", seasons));
            
            bool skipExisting = configuration.GetValue<bool>("Ingest:SkipExistingGames", true);
            int logEveryN = configuration.GetValue<int>("Ingest:LogEveryNGames", 10);

            var allGameIds = new List<(string season, int gameId)>();

            foreach (var season in seasons)
            {
                var gameIds = await apiClient.GetGameIdsForSeasonAsync(season);
                allGameIds.AddRange(gameIds.Select(id => (season, id)));
            }

            var gamesToProcess = allGameIds
                .Where(g => !skipExisting || !existingGameIds.Contains(g.gameId))
                .ToList();

            logger.LogInformation("Total games to process: {Count} (skipped {Skipped} existing)",
                gamesToProcess.Count, allGameIds.Count - gamesToProcess.Count);

            int processed = 0;
            int succeeded = 0;
            int failed = 0;
            int skipped = 0;

            foreach (var (season, gameId) in gamesToProcess)
            {
                processed++;

                try
                {
                    var success = await gameIngester.IngestGameAsync(gameId);
                    if (success)
                    {
                        succeeded++;
                    }
                    else
                    {
                        skipped++;
                        logger.LogDebug("Game {GameId} skipped (no data available)", gameId);
                    }

                    if (processed % logEveryN == 0)
                    {
                        logger.LogInformation("Progress: {Processed}/{Total} games. {Succeeded} ok, {Skipped} skipped, {Failed} failed.",
                            processed, gamesToProcess.Count, succeeded, skipped, failed);
                    }
                }
                catch (Exception ex)
                {
                    failed++;
                    logger.LogError(ex, "Exception processing game {GameId}: {Message}", gameId, ex.Message);
                }

                await Task.Delay(configuration.GetValue<int>("NhlApi:DelayMs", 500));
            }

            logger.LogInformation("Ingestion complete. Processed: {Processed}, Succeeded: {Succeeded}, Skipped: {Skipped}, Failed: {Failed}",
                processed, succeeded, skipped, failed);
        }
        catch (Exception ex)
        {
            logger.LogCritical(ex, "Fatal error during ingestion.");
            Environment.Exit(1);
        }
    }

    private static void ConfigureServices(IServiceCollection services, IConfiguration configuration)
    {
        services.AddLogging(builder =>
        {
            builder.AddConsole();
            builder.SetMinimumLevel(LogLevel.Information);
            builder.AddFilter("System.Net.Http.HttpClient", LogLevel.Warning);
        });

        services.AddSingleton(configuration);

        services.AddSingleton(sp =>
        {
            var client = new HttpClient
            {
                Timeout = TimeSpan.FromSeconds(30)
            };
            var config = sp.GetRequiredService<IConfiguration>();
            var logger = sp.GetRequiredService<ILogger<NhlApiClient>>();
            return new NhlApiClient(client, config, logger);
        });

        services.AddSingleton(sp =>
        {
            var connString = configuration.GetConnectionString("DefaultConnection")
                ?? throw new InvalidOperationException("Connection string not found.");
            return new DatabaseManager(connString, sp.GetRequiredService<ILogger<DatabaseManager>>());
        });
        services.AddSingleton<PossessionTracker>();
        services.AddSingleton<GameIngester>();
    }
}