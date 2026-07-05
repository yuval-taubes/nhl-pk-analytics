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

app.MapGet("/api/analytics/v2/latest-run", (IConfiguration config, IWebHostEnvironment env) =>
{
    var result = TryLoadLatestV2Run(config, env);
    return result.Run is null
        ? Results.NotFound(new { error = result.Error })
        : Results.Json(result.Run);
});

app.MapGet("/api/analytics/v2/models", (IConfiguration config, IWebHostEnvironment env) =>
{
    var result = TryLoadLatestV2Run(config, env);
    if (result.Run is null)
    {
        return Results.NotFound(new { error = result.Error });
    }

    var models = result.Run["models"]?.AsObject()
        .Select(model => ToModelCard(model.Key, model.Value))
        .ToArray() ?? [];

    return Results.Ok(new
    {
        version = StringValue(result.Run["version"]),
        source = result.Run["source"],
        startedAt = StringValue(result.Run["started_at"]),
        completedAt = StringValue(result.Run["completed_at"]),
        models,
    });
});

app.MapGet("/api/analytics/v2/models/{modelKey}", (string modelKey, IConfiguration config, IWebHostEnvironment env) =>
{
    var result = TryLoadLatestV2Run(config, env);
    if (result.Run is null)
    {
        return Results.NotFound(new { error = result.Error });
    }

    var model = FindV2Model(result.Run, modelKey);
    return model is null
        ? Results.NotFound(new { error = $"V2 model {modelKey} was not found in the latest analytics run." })
        : Results.Json(model);
});

app.MapGet("/api/analytics/v2/dashboard", (IConfiguration config, IWebHostEnvironment env) =>
{
    var result = TryLoadLatestV2Run(config, env);
    if (result.Run is null)
    {
        return Results.NotFound(new { error = result.Error });
    }

    var run = result.Run;
    var movement = FindV2Model(run, "PuckMovementGeometryModel");
    var aftershock = FindV2Model(run, "BlockedShotAftershockModel");
    var goalie = FindV2Model(run, "GoalieControlAboveExpectedModel");
    var fatigue = FindV2Model(run, "PkFatigueTimingModel");
    var twoWay = FindV2Model(run, "ShortHandedTwoWayValueModel");
    var bayesian = FindV2Model(run, "BayesianPkPlayerEvaluationModel");
    var playerTags = FindV2Model(run, "PlayerTaggingModel");
    var rushSet = FindV2Model(run, "RushSetDefenseModel");
    var matchups = FindV2Model(run, "SpecialTeamsMatchupModel");

    var reboundBucket = FindByString(movement?["bucket_summary"], "movement_bucket", "rebound");
    var northSouthBucket = FindByString(movement?["bucket_summary"], "movement_bucket", "north_south_downhill");
    var blockLeague = aftershock?["league"];
    var rushSample = IntValue(rushSet?["sample"]?["rush_flagged_shots"]);

    return Results.Ok(new
    {
        latestRun = new
        {
            startedAt = StringValue(run["started_at"]),
            completedAt = StringValue(run["completed_at"]),
            fileName = Path.GetFileName(result.Path),
        },
        version = StringValue(run["version"]),
        source = run["source"],
        metrics = new[]
        {
            new
            {
                label = "PK Shots Against",
                value = IntValue(movement?["sample"]?["pk_shots_against"]).ToString("N0"),
                delta = "MoneyPuck v2",
                intent = "flat",
                helper = "Validated special-teams shot sample",
            },
            new
            {
                label = "Rebound Avg xG",
                value = FormatNumber(NumberValue(reboundBucket?["avg_xg"]), "0.000"),
                delta = "movement",
                intent = "down",
                helper = "Highest-danger movement bucket",
            },
            new
            {
                label = "North-South xG",
                value = FormatNumber(NumberValue(northSouthBucket?["avg_xg"]), "0.000"),
                delta = "downhill",
                intent = "down",
                helper = "Downhill pressure into the slot",
            },
            new
            {
                label = "After-Block Shots",
                value = IntValue(blockLeague?["after_block_shots"]).ToString("N0"),
                delta = "pressure",
                intent = "flat",
                helper = "Shots after failed block clearances",
            },
            new
            {
                label = "Rush Sample",
                value = rushSample.ToString("N0"),
                delta = "diagnostic",
                intent = "flat",
                helper = "Sparse MoneyPuck rush flag",
            },
        },
        takeaways = new[]
        {
            new
            {
                title = "Rebounds are the clearest second-chance danger",
                value = FormatNumber(NumberValue(reboundBucket?["avg_xg"]), "0.000"),
                detail = "Rebound shots had the highest average danger. The first save or block did not finish the play.",
                tone = "bad",
            },
            new
            {
                title = "A block only helps if the PK wins the next puck",
                value = FormatNumber(NumberValue(blockLeague?["league_avg_xg_after_block"]), "0.000"),
                detail = "This measures the next recorded shot after a blocked attempt, where failed recoveries still become chances.",
                tone = "warn",
            },
            new
            {
                title = "Goalie control is the save and the next play",
                value = "v2",
                detail = "The goalie model looks at goals saved, rebounds, freezes, and whether the puck stays dangerous.",
                tone = "good",
            },
        },
        forayRows = new JsonArray(),
        entryRows = new JsonArray(),
        faceoffRows = new JsonArray(),
        playerLeaders = new
        {
            forwards = new JsonArray(),
            defensemen = new JsonArray(),
            centers = new JsonArray(),
            shotBlockers = new JsonArray(),
        },
        movementRows = movement?["bucket_summary"] ?? new JsonArray(),
        aftershockTeams = TakeArray(aftershock?["highest_aftershock_teams"], 8),
        goalieControl = TakeTopPerSeason(goalie?["goalies"], "control_score", descending: true, count: 4),
        reboundLeakWatch = TakeTopPerSeason(goalie?["goalies"], "rebounds_allowed_above_expected_per100", descending: true, count: 4),
        fatigueRows = fatigue?["defending_average_toi"] ?? new JsonArray(),
        penaltyTimingRows = fatigue?["penalty_elapsed"] ?? new JsonArray(),
        twoWayLeaders = TakeTopPerSeason(twoWay?["players"], "two_way_net_xg_per60", descending: true, count: 6),
        offenseWithoutLeakage = TakeTopPerSeason(
            twoWay?["players"],
            "two_way_net_xg_per60",
            descending: true,
            count: 6,
            predicate: player => NumberValue(player?["offense_percentile"]) >= 70 && NumberValue(player?["defense_percentile"]) >= 45),
        trustedPkImpact = TakeTopPerSeason(bayesian?["trusted_pk_impact"], "true_talent_pk_impact_per60", descending: true, count: 6),
        highUpsideNoisy = TakeTopPerSeason(bayesian?["high_upside_noisy"], "true_talent_pk_impact_per60", descending: true, count: 6),
        playerSimilarityGroups = TakeTopPerSeason(bayesian?["similarity_groups"], "true_talent_pk_impact_per60", descending: true, count: 3),
        playerTagProfiles = TakePlayerTagProfiles(
            playerTags?["player_profiles"],
            matchups?["team_shot_maps"],
            latestSeasonTeams: 16,
            historySeasonTeams: 4,
            profilesPerTeam: 1),
        playerTagDictionary = playerTags?["tag_dictionary"] ?? new JsonArray(),
        scoutingSeasons = BuildSeasonArray(twoWay?["seasons"], goalie?["seasons"], bayesian?["seasons"], playerTags?["seasons"]),
        rushSetSummary = rushSet?["summary"] ?? new JsonArray(),
        leagueAttackTypes = TakeLatestSeasonTop(matchups?["league_attack_types"], "xg", descending: true, count: 8),
        ppAttackProfiles = TakeTeamProfilesPerSeason(matchups?["pp_attack_profiles"], "style_score", teamsPerSeason: 6, rowsPerTeam: 3),
        pkLeakProfiles = TakeLatestSeasonTop(matchups?["pk_leak_profiles"], "style_score", descending: true, count: 24),
        matchupCards = TakeArray(matchups?["matchup_cards"], 24),
        leaguePkDangerHeatmap = TakeArray(matchups?["league_pk_danger_heatmap"], 50),
        teamShotMaps = TakeTeamShotMaps(matchups?["team_shot_maps"], latestSeasonTeams: 16, historySeasonTeams: 4, latestRowsPerTeamProfile: 7, historyRowsPerTeamProfile: 4),
        modelCards = run["models"]?.AsObject()
            .Select(model => ToModelCard(model.Key, model.Value))
            .ToArray() ?? [],
        caveats = new[]
        {
            "MoneyPuck is the source for v2 shot quality and outcome probabilities; credit MoneyPuck.com.",
            "V2 movement buckets are derived from shot and last-event coordinates, not player tracking.",
            "Old NHL API models remain available as legacy context but are no longer the primary analytics layer.",
        },
    });
});

app.Run();

static (JsonNode? Run, string? Path, string? Error) TryLoadLatestRun(IConfiguration config, IWebHostEnvironment env)
{
    return TryLoadLatestRunPattern(config, env, "models_2_10_run_*.json");
}

static (JsonNode? Run, string? Path, string? Error) TryLoadLatestV2Run(IConfiguration config, IWebHostEnvironment env)
{
    return TryLoadLatestRunPattern(config, env, "models_v2_run_*.json");
}

static (JsonNode? Run, string? Path, string? Error) TryLoadLatestRunPattern(IConfiguration config, IWebHostEnvironment env, string filePattern)
{
    var configuredPath = config["AnalyticsOutputPath"];
    var outputPath = BuildOutputPathCandidates(configuredPath, env.ContentRootPath)
        .FirstOrDefault(Directory.Exists);

    if (outputPath is null)
    {
        return (null, null, "Analytics output folder not found. Check AnalyticsOutputPath in NhlPkApi/appsettings.json.");
    }

    var latest = Directory
        .EnumerateFiles(outputPath, filePattern)
        .Select(path => new FileInfo(path))
        .OrderByDescending(file => RunTimestamp(file) ?? file.LastWriteTimeUtc)
        .FirstOrDefault();

    if (latest is null)
    {
        return (null, null, $"No combined analytics run files matching {filePattern} were found in {outputPath}.");
    }

    using var stream = latest.OpenRead();
    return (JsonNode.Parse(stream), latest.FullName, null);
}

static DateTime? RunTimestamp(FileInfo file)
{
    var name = Path.GetFileNameWithoutExtension(file.Name);
    var parts = name.Split('_');
    if (parts.Length < 2)
    {
        return null;
    }

    var timestamp = $"{parts[^2]}_{parts[^1]}";
    return DateTime.TryParseExact(
        timestamp,
        "yyyyMMdd_HHmmss",
        CultureInfo.InvariantCulture,
        DateTimeStyles.AssumeLocal,
        out var parsed)
        ? parsed.ToUniversalTime()
        : null;
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
        .FirstOrDefault(model => string.Equals(model.Key, ModelKey(modelNumber), StringComparison.OrdinalIgnoreCase))
        .Value;
}

static JsonNode? FindV2Model(JsonNode run, string modelKey)
{
    var models = run["models"]?.AsObject();
    if (models is null)
    {
        return null;
    }

    return models
        .FirstOrDefault(model => string.Equals(model.Key, modelKey, StringComparison.OrdinalIgnoreCase))
        .Value;
}

static string ModelKey(int modelNumber) => modelNumber switch
{
    2 => "PkRushCommitmentModel",
    3 => "IntentionalClearanceFaceoffModel",
    4 => "PkForecheckStructureModel",
    5 => "PkFaceoffModel",
    6 => "ForwardForecheckingModel",
    7 => "DefenseGapControlModel",
    8 => "ForwardShotSuppressionModel",
    9 => "CenterFaceoffValueModel",
    10 => "NetFrontDefenseModel",
    _ => "",
};

static JsonArray TakeArray(JsonNode? arrayNode, int count)
{
    var output = new JsonArray();
    var array = arrayNode?.AsArray();
    if (array is null)
    {
        return output;
    }

    foreach (var item in array.Take(count))
    {
        output.Add(item?.DeepClone());
    }

    return output;
}

static JsonArray TakeTopPerSeason(
    JsonNode? arrayNode,
    string sortProperty,
    bool descending,
    int count,
    Func<JsonNode?, bool>? predicate = null)
{
    var output = new JsonArray();
    var array = arrayNode?.AsArray();
    if (array is null)
    {
        return output;
    }

    var rows = array
        .Where(item => predicate?.Invoke(item) ?? true)
        .GroupBy(item => IntValue(item?["season"]))
        .Where(group => group.Key > 0);

    foreach (var group in rows.OrderByDescending(group => group.Key))
    {
        var sorted = descending
            ? group.OrderByDescending(item => NumberValue(item?[sortProperty]) ?? double.MinValue)
            : group.OrderBy(item => NumberValue(item?[sortProperty]) ?? double.MaxValue);

        foreach (var item in sorted.Take(count))
        {
            output.Add(item?.DeepClone());
        }
    }

    return output;
}

static JsonArray TakeLatestSeasonTop(
    JsonNode? arrayNode,
    string sortProperty,
    bool descending,
    int count,
    Func<JsonNode?, bool>? predicate = null)
{
    var output = new JsonArray();
    var array = arrayNode?.AsArray();
    if (array is null)
    {
        return output;
    }

    var rows = array
        .Where(item => predicate?.Invoke(item) ?? true)
        .Where(item => IntValue(item?["season"]) > 0)
        .ToArray();
    if (rows.Length == 0)
    {
        return output;
    }

    var latestSeason = rows.Max(item => IntValue(item?["season"]));
    var latestRows = rows.Where(item => IntValue(item?["season"]) == latestSeason);
    var sorted = descending
        ? latestRows.OrderByDescending(item => NumberValue(item?[sortProperty]) ?? double.MinValue)
        : latestRows.OrderBy(item => NumberValue(item?[sortProperty]) ?? double.MaxValue);

    foreach (var item in sorted.Take(count))
    {
        output.Add(item?.DeepClone());
    }

    return output;
}

static JsonArray TakeTeamProfilesPerSeason(JsonNode? arrayNode, string sortProperty, int teamsPerSeason, int rowsPerTeam)
{
    var output = new JsonArray();
    var array = arrayNode?.AsArray();
    if (array is null)
    {
        return output;
    }

    var rows = array
        .Where(item => IntValue(item?["season"]) > 0 && !string.IsNullOrWhiteSpace(StringValue(item?["team"])))
        .GroupBy(item => IntValue(item?["season"]));

    foreach (var seasonGroup in rows.OrderByDescending(group => group.Key))
    {
        var teamGroups = seasonGroup
            .GroupBy(item => StringValue(item?["team"]))
            .Select(group => new
            {
                Team = group.Key,
                Rows = group
                    .OrderByDescending(item => NumberValue(item?[sortProperty]) ?? double.MinValue)
                    .Take(rowsPerTeam)
                    .ToArray(),
                Score = group.Max(item => NumberValue(item?[sortProperty]) ?? double.MinValue),
            })
            .OrderByDescending(group => group.Score)
            .Take(teamsPerSeason);

        foreach (var teamGroup in teamGroups)
        {
            foreach (var item in teamGroup.Rows)
            {
                output.Add(item?.DeepClone());
            }
        }
    }

    return output;
}

static JsonArray TakeTeamShotMaps(
    JsonNode? arrayNode,
    int latestSeasonTeams,
    int historySeasonTeams,
    int latestRowsPerTeamProfile,
    int historyRowsPerTeamProfile)
{
    var output = new JsonArray();
    var array = arrayNode?.AsArray();
    if (array is null)
    {
        return output;
    }

    var rows = array
        .Where(item => IntValue(item?["season"]) > 0
            && !string.IsNullOrWhiteSpace(StringValue(item?["team"]))
            && !string.IsNullOrWhiteSpace(StringValue(item?["profile_type"])))
        .GroupBy(item => IntValue(item?["season"]));

    var orderedSeasons = rows.OrderByDescending(group => group.Key).ToArray();
    var latestSeason = orderedSeasons.FirstOrDefault()?.Key;

    foreach (var seasonGroup in orderedSeasons)
    {
        var isLatestSeason = latestSeason.HasValue && seasonGroup.Key == latestSeason.Value;
        var teamsPerSeason = isLatestSeason ? latestSeasonTeams : historySeasonTeams;
        var rowsPerTeamProfile = isLatestSeason ? latestRowsPerTeamProfile : historyRowsPerTeamProfile;
        var teamScores = seasonGroup
            .GroupBy(item => StringValue(item?["team"]))
            .Select(group => new
            {
                Team = group.Key,
                Score = group.Max(item => NumberValue(item?["map_score"]) ?? NumberValue(item?["xg"]) ?? double.MinValue),
            })
            .OrderByDescending(group => group.Score)
            .Take(teamsPerSeason)
            .Select(group => group.Team)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);

        var profileGroups = seasonGroup
            .Where(item => teamScores.Contains(StringValue(item?["team"])))
            .GroupBy(item => $"{StringValue(item?["team"])}|{StringValue(item?["profile_type"])}");

        foreach (var profileGroup in profileGroups)
        {
            var sorted = profileGroup
                .OrderByDescending(item => NumberValue(item?["map_score"]) ?? NumberValue(item?["xg"]) ?? double.MinValue)
                .Take(rowsPerTeamProfile);

            foreach (var item in sorted)
            {
                output.Add(ToCompactShotMapBin(item));
            }
        }
    }

    return output;
}

static JsonObject ToCompactShotMapBin(JsonNode? item)
{
    return new JsonObject
    {
        ["season"] = IntValue(item?["season"]),
        ["team"] = StringValue(item?["team"]),
        ["profile_type"] = StringValue(item?["profile_type"]),
        ["attack_type"] = StringValue(item?["attack_type"]),
        ["x_bin"] = IntValue(item?["x_bin"]),
        ["y_bin"] = IntValue(item?["y_bin"]),
        ["rink_x"] = NumberValue(item?["rink_x"]),
        ["rink_y"] = NumberValue(item?["rink_y"]),
        ["shots"] = IntValue(item?["shots"]),
        ["xg"] = NumberValue(item?["xg"]),
        ["avg_xg"] = NumberValue(item?["avg_xg"]),
        ["xg_share"] = NumberValue(item?["xg_share"]),
        ["shot_share"] = NumberValue(item?["shot_share"]),
        ["goal_rate"] = NumberValue(item?["goal_rate"]),
        ["rebound_rate"] = NumberValue(item?["rebound_rate"]),
        ["royal_road_rate"] = NumberValue(item?["royal_road_rate"]),
        ["map_score"] = NumberValue(item?["map_score"]),
    };
}

static JsonArray TakePlayerTagProfiles(
    JsonNode? arrayNode,
    JsonNode? teamShotMapsNode,
    int latestSeasonTeams,
    int historySeasonTeams,
    int profilesPerTeam)
{
    var output = new JsonArray();
    var array = arrayNode?.AsArray();
    if (array is null)
    {
        return output;
    }

    var teamsBySeason = TeamShotMapTeamsBySeason(teamShotMapsNode, latestSeasonTeams, historySeasonTeams);
    var rows = array
        .Where(item => IntValue(item?["season"]) > 0)
        .GroupBy(item => IntValue(item?["season"]));

    foreach (var group in rows.OrderByDescending(group => group.Key))
    {
        if (!teamsBySeason.TryGetValue(group.Key, out var seasonTeams))
        {
            continue;
        }

        var teamGroups = group
            .Where(item => ProfileTeamsIntersect(StringValue(item?["teams"]), seasonTeams))
            .GroupBy(item => StringValue(item?["teams"]));

        foreach (var teamGroup in teamGroups.OrderBy(teamGroup => teamGroup.Key))
        {
            var sorted = teamGroup
                .OrderByDescending(item => NumberValue(item?["supporting_signal_count"]) ?? 0)
                .ThenByDescending(item => NumberValue(item?["ice_time"]) ?? 0)
                .ThenByDescending(item => NumberValue(item?["true_talent_pk_impact_per60"]) ?? double.MinValue);
            foreach (var item in sorted.Take(profilesPerTeam))
            {
                output.Add(ToCompactPlayerTagProfile(item));
            }
        }
    }

    return output;
}

static bool ProfileTeamsIntersect(string profileTeams, HashSet<string> selectedTeams)
{
    if (string.IsNullOrWhiteSpace(profileTeams) || selectedTeams.Count == 0)
    {
        return false;
    }

    var tokens = profileTeams
        .Split(new[] { '/', ',', '|', ' ' }, StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    return tokens.Any(selectedTeams.Contains);
}

static Dictionary<int, HashSet<string>> TeamShotMapTeamsBySeason(JsonNode? arrayNode, int latestSeasonTeams, int historySeasonTeams)
{
    var result = new Dictionary<int, HashSet<string>>();
    var array = arrayNode?.AsArray();
    if (array is null)
    {
        return result;
    }

    var rows = array
        .Where(item => IntValue(item?["season"]) > 0 && !string.IsNullOrWhiteSpace(StringValue(item?["team"])))
        .GroupBy(item => IntValue(item?["season"]))
        .OrderByDescending(group => group.Key)
        .ToArray();
    var latestSeason = rows.FirstOrDefault()?.Key;

    foreach (var seasonGroup in rows)
    {
        var teamsPerSeason = latestSeason.HasValue && seasonGroup.Key == latestSeason.Value ? latestSeasonTeams : historySeasonTeams;
        var teams = seasonGroup
            .GroupBy(item => StringValue(item?["team"]))
            .Select(group => new
            {
                Team = group.Key,
                Score = group.Max(item => NumberValue(item?["map_score"]) ?? NumberValue(item?["xg"]) ?? double.MinValue),
            })
            .OrderByDescending(group => group.Score)
            .Take(teamsPerSeason)
            .Select(group => group.Team)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        result[seasonGroup.Key] = teams;
    }

    return result;
}

static JsonObject ToCompactPlayerTagProfile(JsonNode? item)
{
    return new JsonObject
    {
        ["player_id"] = IntValue(item?["player_id"]),
        ["name"] = StringValue(item?["name"]),
        ["position"] = StringValue(item?["position"]),
        ["season"] = IntValue(item?["season"]),
        ["teams"] = StringValue(item?["teams"]),
        ["ice_time"] = NumberValue(item?["ice_time"]),
        ["games_played"] = IntValue(item?["games_played"]),
        ["on_ice_sh_xg_for_per60"] = NumberValue(item?["on_ice_sh_xg_for_per60"]),
        ["on_ice_xga_per60"] = NumberValue(item?["on_ice_xga_per60"]),
        ["two_way_net_xg_per60"] = NumberValue(item?["two_way_net_xg_per60"]),
        ["individual_sh_xg_per60"] = NumberValue(item?["individual_sh_xg_per60"]),
        ["shot_attempt_share"] = NumberValue(item?["shot_attempt_share"]),
        ["blocks_per60"] = NumberValue(item?["blocks_per60"]),
        ["penalty_draw_minus_take_per60"] = NumberValue(item?["penalty_draw_minus_take_per60"]),
        ["true_talent_pk_impact_per60"] = NumberValue(item?["true_talent_pk_impact_per60"]),
        ["impact_lower_90"] = NumberValue(item?["impact_lower_90"]),
        ["impact_upper_90"] = NumberValue(item?["impact_upper_90"]),
        ["trust_label"] = StringValue(item?["trust_label"]),
        ["trust_level"] = StringValue(item?["trust_level"]),
        ["sample_trust"] = StringValue(item?["sample_trust"]),
        ["sample_trust_label"] = StringValue(item?["sample_trust_label"]),
        ["sample_trust_sentence"] = StringValue(item?["sample_trust_sentence"]),
        ["supporting_signal_count"] = IntValue(item?["supporting_signal_count"]),
        ["rate_sensitive_tag_count"] = IntValue(item?["rate_sensitive_tag_count"]),
        ["summary_sentence"] = StringValue(item?["summary_sentence"]),
        ["tags"] = CompactTags(item?["tags"], 6),
        ["top_strengths"] = CompactTags(item?["top_strengths"], 3),
        ["main_risks"] = CompactTags(item?["main_risks"], 3),
    };
}

static JsonArray CompactTags(JsonNode? tagsNode, int count)
{
    var output = new JsonArray();
    var tags = tagsNode?.AsArray();
    if (tags is null)
    {
        return output;
    }

    foreach (var tag in tags.Take(count))
    {
        output.Add(new JsonObject
        {
            ["tag_id"] = StringValue(tag?["tag_id"]),
            ["label"] = StringValue(tag?["label"]),
            ["category"] = StringValue(tag?["category"]),
            ["confidence"] = StringValue(tag?["confidence"]),
            ["sample_confidence"] = StringValue(tag?["sample_confidence"]),
            ["tag_strength"] = StringValue(tag?["tag_strength"]),
            ["priority_label"] = StringValue(tag?["priority_label"]),
            ["reason"] = StringValue(tag?["reason"]),
            ["sample_size_note"] = StringValue(tag?["sample_size_note"]),
            ["higher_is_better"] = BoolValue(tag?["higher_is_better"]),
            ["league_percentile"] = NumberValue(tag?["league_percentile"]),
        });
    }

    return output;
}

static JsonArray BuildSeasonArray(params JsonNode?[] seasonNodes)
{
    var seasons = new SortedSet<int>(Comparer<int>.Create((left, right) => right.CompareTo(left)));

    foreach (var node in seasonNodes)
    {
        var array = node?.AsArray();
        if (array is null)
        {
            continue;
        }

        foreach (var item in array)
        {
            var value = IntValue(item);
            if (value > 0)
            {
                seasons.Add(value);
            }
        }
    }

    var output = new JsonArray();
    foreach (var season in seasons)
    {
        output.Add(season);
    }

    return output;
}

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
        ? players.OrderByDescending(player => NumberValue(player?[metric]) ?? double.NegativeInfinity)
        : players.OrderBy(player => NumberValue(player?[metric]) ?? double.PositiveInfinity);

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

static double? NumberValue(JsonNode? node)
{
    if (node is null)
    {
        return null;
    }

    try
    {
        return node.GetValue<double>();
    }
    catch (InvalidOperationException)
    {
        return double.TryParse(StringValue(node), NumberStyles.Float, CultureInfo.InvariantCulture, out var value)
            ? value
            : null;
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
        return (int)Math.Round(NumberValue(node) ?? 0);
    }
}

static bool BoolValue(JsonNode? node)
{
    if (node is null)
    {
        return false;
    }

    try
    {
        return node.GetValue<bool>();
    }
    catch (InvalidOperationException)
    {
        return bool.TryParse(StringValue(node), out var value) && value;
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

static string FormatNumber(double? value, string format)
{
    return value.HasValue ? value.Value.ToString(format) : "N/A";
}

static string FormatSigned(double? value, string format)
{
    if (!value.HasValue)
    {
        return "N/A";
    }

    return value.Value > 0 ? $"+{value.Value.ToString(format)}" : value.Value.ToString(format);
}
