using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using NhlPkIngest.Services;

namespace NhlPkIngest;

class Program
{
    static async Task Main(string[] args)
    {
        // Build configuration
        var configuration = new ConfigurationBuilder()
            .SetBasePath(Directory.GetCurrentDirectory())
            .AddJsonFile("appsettings.json", optional: false)
            .AddEnvironmentVariables()
            .AddCommandLine(args)
            .Build();

        // Setup DI
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

            // Initialize schema
            await dbManager.InitializeSchemaAsync();

            // Get existing game IDs to skip
            var existingGameIds = await dbManager.GetExistingGameIdsAsync();

            // Get seasons to process
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

            // Filter out existing games
            var gamesToProcess = allGameIds
                .Where(g => !skipExisting || !existingGameIds.Contains(g.gameId))
                .ToList();

            logger.LogInformation("Total games to process: {Count} (skipped {Skipped} existing)",
                gamesToProcess.Count, allGameIds.Count - gamesToProcess.Count);

            int processed = 0;
            int succeeded = 0;
            int failed = 0;

            foreach (var (season, gameId) in gamesToProcess)
            {
                processed++;

                try
                {
                    var success = await gameIngester.IngestGameAsync(gameId);
                    if (success)
                        succeeded++;
                    else
                        failed++;

                    if (processed % logEveryN == 0)
                    {
                        logger.LogInformation("Progress: {Processed}/{Total} games. {Succeeded} succeeded, {Failed} failed.",
                            processed, gamesToProcess.Count, succeeded, failed);
                    }
                }
                catch (Exception ex)
                {
                    failed++;
                    logger.LogError(ex, "Failed to process game {GameId}", gameId);
                }

                // Rate limiting
                await Task.Delay(configuration.GetValue<int>("NhlApi:DelayMs", 500));
            }

            logger.LogInformation("Ingestion complete. Processed: {Processed}, Succeeded: {Succeeded}, Failed: {Failed}",
                processed, succeeded, failed);
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
            builder.SetMinimumLevel(LogLevel.Debug);  // Changed from Information to Debug
            builder.AddFilter("System.Net.Http.HttpClient", LogLevel.Warning);
        });

        services.AddSingleton(configuration);
        services.AddHttpClient<NhlApiClient>();
        services.AddSingleton<NhlApiClient>();
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