using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddCors(options =>
{
    options.AddPolicy(
        "Frontend",
        policy => policy
            .WithOrigins(
                "http://localhost:5173",
                "http://localhost:5174",
                "http://127.0.0.1:5173",
                "http://127.0.0.1:5174")
            .AllowAnyHeader()
            .AllowAnyMethod());
});

builder.Services.ConfigureHttpJsonOptions(options =>
{
    options.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;
});

var app = builder.Build();

app.UseCors("Frontend");

app.MapGet("/api/health", () => Results.Ok(new { status = "ok", service = "NHL PK API" }));

app.MapGet("/api/analytics/latest-run", (IConfiguration config, IWebHostEnvironment env) =>
{
    var result = TryLoadLatestRun(config, env);
    return result.Run is null
        ? Results.NotFound(new { error = result.Error })
        : Results.Json(result.Run);
});

app.MapGet("/api/analytics/models", (IConfiguration config, IWebHostEnvironment env) =>
{
    var result = TryLoadLatestRun(config, env);
    if (result.Run is null)
    {
        return Results.NotFound(new { error = result.Error });
    }

    var models = result.Run["models"]?.AsObject()
        .Select(model => ToModelCard(model.Key, model.Value))
        .ToArray() ?? [];

    return Results.Ok(new
    {
        startedAt = StringValue(result.Run["started_at"]),
        completedAt = StringValue(result.Run["completed_at"]),
        models,
    });
});

app.MapGet("/api/analytics/models/{modelNumber:int}", (int modelNumber, IConfiguration config, IWebHostEnvironment env) =>
{
    var result = TryLoadLatestRun(config, env);
    if (result.Run is null)
    {
        return Results.NotFound(new { error = result.Error });
    }

    var model = FindModel(result.Run, modelNumber);
    return model is null
        ? Results.NotFound(new { error = $"Model {modelNumber} was not found in the latest analytics run." })
        : Results.Json(model);
});

app.MapGet("/api/analytics/dashboard", (IConfiguration config, IWebHostEnvironment env) =>
{
    var result = TryLoadLatestRun(config, env);
    if (result.Run is null)
    {
        return Results.NotFound(new { error = result.Error });
    }

    var run = result.Run;
    var model2 = FindModel(run, 2);
    var model3 = FindModel(run, 3);
    var model4 = FindModel(run, 4);
    var model5 = FindModel(run, 5);
    var model6 = FindModel(run, 6);
    var model7 = FindModel(run, 7);
    var model8 = FindModel(run, 8);
    var model9 = FindModel(run, 9);
    var model10 = FindModel(run, 10);

    var faceoffEffect = NumberValue(model5?["estimated_effect"]?["att_win_vs_loss_xga_20"]);
    var maintainNet = FindByString(model3?["path_summary"], "path", "maintain_play")?["avg_net_xg_20"];
    var outOfPlayNet = FindByString(model3?["path_summary"], "path", "out_of_play")?["avg_net_xg_20"];
    var controlledEntry = FindByString(model4?["summary_by_entry_type"], "entry_type", "CONTROLLED");
    var dumpEntry = FindByString(model4?["summary_by_entry_type"], "entry_type", "DUMP_IN");

    return Results.Ok(new
    {
        latestRun = new
        {
            startedAt = StringValue(run["started_at"]),
            completedAt = StringValue(run["completed_at"]),
            fileName = Path.GetFileName(result.Path),
        },
        metrics = new[]
        {
            new
            {
                label = "DZ Faceoff xGA Saved",
                value = FormatSigned(faceoffEffect, "0.000"),
                delta = "next 20s",
                intent = "down",
                helper = "Matched PK win vs loss effect",
            },
            new
            {
                label = "OZ Faceoff EV",
                value = FormatSigned(NumberValue(model3?["oz_faceoff_ev"]?["ev_out_of_play"]), "0.000"),
                delta = "net xG",
                intent = "up",
                helper = "Forcing whistle/OZ faceoff",
            },
            new
            {
                label = "PK OZ Forays",
                value = IntValue(model2?["sample"]?["n_forays"]).ToString("N0"),
                delta = "sample",
                intent = "flat",
                helper = "Short-handed OZ possessions",
            },
            new
            {
                label = "Player Scouting Rows",
                value = (
                    IntValue(model6?["scouting_rows_exported"]) +
                    IntValue(model7?["scouting_rows_exported"]) +
                    IntValue(model8?["scouting_rows_exported"]) +
                    IntValue(model9?["scouting_rows_exported"]) +
                    IntValue(model10?["scouting_rows_exported"])
                ).ToString("N0"),
                delta = "exported",
                intent = "flat",
                helper = "Event-participant metrics",
            },
        },
        takeaways = new[]
        {
            new
            {
                title = "DZ PK faceoff wins sharply reduce danger",
                value = FormatSigned(faceoffEffect, "0.000"),
                detail = "Estimated xGA change in the next 20 seconds for a PK faceoff win relative to a matched loss.",
                tone = "good",
            },
            new
            {
                title = "OZ whistle is not a free reset",
                value = FormatSigned(NumberValue(outOfPlayNet), "0.000"),
                detail = $"Maintain-play net xG was {FormatSigned(NumberValue(maintainNet), "0.000")} over the same short window.",
                tone = "bad",
            },
            new
            {
                title = "Dump-ins were more dangerous in this run",
                value = FormatNumber(NumberValue(dumpEntry?["avg_xga_per_entry"]), "0.000"),
                detail = $"Controlled entries averaged {FormatNumber(NumberValue(controlledEntry?["avg_xga_per_entry"]), "0.000")} xGA per entry.",
                tone = "warn",
            },
        },
        forayRows = model2?["summary_by_foray_type"] ?? new JsonArray(),
        entryRows = model4?["summary_by_entry_type"] ?? new JsonArray(),
        faceoffRows = model5?["outcome_summary"] ?? new JsonArray(),
        playerLeaders = new
        {
            forwards = TopPlayers(model6, "positive_event_rate", true, 5),
            defensemen = TopPlayers(model7, "disruption_rate", true, 5),
            centers = TopPlayers(model9, "faceoff_value_added", true, 5),
            shotBlockers = TopPlayers(model10, "high_danger_block_rate", true, 5),
        },
        modelCards = run["models"]?.AsObject()
            .Select(model => ToModelCard(model.Key, model.Value))
            .ToArray() ?? [],
        caveats = new[]
        {
            "Player tables are tagged event-participant scouting, not true on-ice impact.",
            "Forecheck shape, gap control, and net-front coverage need shift/tracking data.",
            "Generated analytics JSON is a local artifact; rerun the Python models to refresh it.",
        },
    });
});

app.Run();

static (JsonNode? Run, string? Path, string? Error) TryLoadLatestRun(IConfiguration config, IWebHostEnvironment env)
{
    var configuredPath = config["AnalyticsOutputPath"];
    var outputPath = BuildOutputPathCandidates(configuredPath, env.ContentRootPath)
        .FirstOrDefault(Directory.Exists);

    if (outputPath is null)
    {
        return (null, null, "Analytics output folder not found. Check AnalyticsOutputPath in NhlPkApi/appsettings.json.");
    }

    var latest = Directory
        .EnumerateFiles(outputPath, "models_2_10_run_*.json")
        .Select(path => new FileInfo(path))
        .OrderByDescending(file => file.LastWriteTimeUtc)
        .FirstOrDefault();

    if (latest is null)
    {
        return (null, null, $"No combined analytics run files were found in {outputPath}.");
    }

    using var stream = latest.OpenRead();
    return (JsonNode.Parse(stream), latest.FullName, null);
}

static IEnumerable<string> BuildOutputPathCandidates(string? configuredPath, string contentRootPath)
{
    if (!string.IsNullOrWhiteSpace(configuredPath))
    {
        if (Path.IsPathFullyQualified(configuredPath))
        {
            yield return configuredPath;
        }
        else
        {
            yield return Path.GetFullPath(configuredPath);
            yield return Path.GetFullPath(Path.Combine(contentRootPath, configuredPath));
            yield return Path.GetFullPath(Path.Combine(contentRootPath, "..", configuredPath));
        }
    }

    yield return Path.GetFullPath(Path.Combine(contentRootPath, "Analytics", "models", "output"));
    yield return Path.GetFullPath(Path.Combine(contentRootPath, "..", "Analytics", "models", "output"));
}

static JsonNode? FindModel(JsonNode run, int modelNumber)
{
    var models = run["models"]?.AsObject();
    if (models is null)
    {
        return null;
    }

    return models
        .Select(model => model.Value)
        .FirstOrDefault(model => StringValue(model?["model"]).Contains(ModelKeyword(modelNumber), StringComparison.OrdinalIgnoreCase));
}

static string ModelKeyword(int modelNumber) => modelNumber switch
{
    2 => "Foray",
    3 => "Clearance",
    4 => "Entry Defense",
    5 => "Faceoff Play",
    6 => "Forward Defensive",
    7 => "Defenseman Disruption",
    8 => "Discipline",
    9 => "Center Faceoff",
    10 => "Shot Blocks",
    _ => $"Model {modelNumber}",
};

static object ToModelCard(string key, JsonNode? model)
{
    var sample = model?["sample"]?.AsObject().ToDictionary(
        item => item.Key,
        item => ScalarValue(item.Value));

    return new
    {
        key,
        name = StringValue(model?["model"]),
        outputFile = StringValue(model?["output_file"]),
        computedAt = StringValue(model?["computed_at"]),
        sample,
    };
}

static JsonNode? FindByString(JsonNode? arrayNode, string property, string value)
{
    return arrayNode?.AsArray()
        .FirstOrDefault(item => string.Equals(StringValue(item?[property]), value, StringComparison.OrdinalIgnoreCase));
}

static JsonArray TopPlayers(JsonNode? model, string metric, bool descending, int count)
{
    var players = model?["players"]?.AsArray();
    if (players is null)
    {
        return [];
    }

    var sorted = descending
        ? players.OrderByDescending(player => NumberValue(player?[metric]))
        : players.OrderBy(player => NumberValue(player?[metric]));

    var output = new JsonArray();
    foreach (var player in sorted.Take(count))
    {
        output.Add(player?.DeepClone());
    }

    return output;
}

static string StringValue(JsonNode? node)
{
    if (node is null)
    {
        return "";
    }

    try
    {
        return node.GetValue<string>();
    }
    catch (InvalidOperationException)
    {
        return node.ToJsonString().Trim('"');
    }
}

static double NumberValue(JsonNode? node)
{
    if (node is null)
    {
        return 0;
    }

    try
    {
        return node.GetValue<double>();
    }
    catch (InvalidOperationException)
    {
        return double.TryParse(StringValue(node), NumberStyles.Float, CultureInfo.InvariantCulture, out var value)
            ? value
            : 0;
    }
}

static int IntValue(JsonNode? node)
{
    if (node is null)
    {
        return 0;
    }

    try
    {
        return node.GetValue<int>();
    }
    catch (InvalidOperationException)
    {
        return (int)Math.Round(NumberValue(node));
    }
}

static object? ScalarValue(JsonNode? node)
{
    if (node is null)
    {
        return null;
    }

    try
    {
        return node.GetValue<object>();
    }
    catch (InvalidOperationException)
    {
        return node.ToJsonString();
    }
}

static string FormatNumber(double value, string format)
{
    return value.ToString(format);
}

static string FormatSigned(double value, string format)
{
    return value > 0 ? $"+{value.ToString(format)}" : value.ToString(format);
}
