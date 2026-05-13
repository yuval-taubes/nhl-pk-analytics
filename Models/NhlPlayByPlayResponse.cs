using System.Text.Json.Serialization;

namespace NhlPkIngest.Models;

public class NhlPlayByPlayResponse
{
    [JsonPropertyName("id")]
    public int GameId { get; set; }

    [JsonPropertyName("season")]
    public int Season { get; set; }

    [JsonPropertyName("gameType")]
    public int GameType { get; set; }

    [JsonPropertyName("gameDate")]
    public string? GameDate { get; set; }

    [JsonPropertyName("homeTeam")]
    public NhlTeam? HomeTeam { get; set; }

    [JsonPropertyName("awayTeam")]
    public NhlTeam? AwayTeam { get; set; }

    [JsonPropertyName("plays")]
    public List<NhlPlay>? Plays { get; set; }

[JsonPropertyName("rosterSpots")]
public List<NhlRosterPlayer>? RosterSpots { get; set; }
}

public class NhlTeam
{
    [JsonPropertyName("id")]
    public int Id { get; set; }

    [JsonPropertyName("commonName")]
    public NhlLocalizedName? CommonName { get; set; }

    [JsonPropertyName("abbrev")]
    public string? Abbrev { get; set; }

    [JsonPropertyName("score")]
    public int Score { get; set; }

    public string Name => CommonName?.Default ?? "";
}

public class NhlLocalizedName
{
    [JsonPropertyName("default")]
    public string? Default { get; set; }
}

public class NhlPlay
{
    [JsonPropertyName("eventId")]
    public int EventId { get; set; }

    [JsonPropertyName("periodDescriptor")]
    public NhlPeriodDescriptor? PeriodDescriptor { get; set; }

    [JsonPropertyName("timeInPeriod")]
    public string? TimeInPeriod { get; set; }

    [JsonPropertyName("timeRemaining")]
    public string? TimeRemaining { get; set; }

    [JsonPropertyName("situationCode")]
    public string? SituationCode { get; set; }

    [JsonPropertyName("typeDescKey")]
    public string? TypeDescKey { get; set; }

    [JsonPropertyName("typeCode")]
    public int TypeCode { get; set; }

    [JsonPropertyName("details")]
    public NhlPlayDetails? Details { get; set; }
    
    // Computed helpers
    [JsonIgnore]
    public int Period => PeriodDescriptor?.Number ?? 0;
    
    [JsonIgnore]
    public int? TeamId => Details?.EventOwnerTeamId;
    
    [JsonIgnore]
    public string ZoneCode => Details?.ZoneCode ?? "";
    
    [JsonIgnore]
    public int? XCoord => Details?.XCoord;
    
    [JsonIgnore]
    public int? YCoord => Details?.YCoord;
    
    [JsonIgnore]
    public string StrengthCode => ParseStrengthFromSituationCode(SituationCode);
    
    private static string ParseStrengthFromSituationCode(string? code)
    {
    if (string.IsNullOrEmpty(code) || code.Length < 4) return "EV";
    
    // NHL situation code format: [awayGoalie][awaySkaters][homeSkaters][homeGoalie]
    // "1551" = 1 G + 5 skaters vs 5 skaters + 1 G = 5v5
    // "1541" = 1 G + 5 skaters vs 4 skaters + 1 G = 5v4 (home shorthanded)
    // "1451" = 1 G + 4 skaters vs 5 skaters + 1 G = 4v5 (away shorthanded)
    // "0651" = 0 G + 6 skaters vs 5 skaters + 1 G = 6v5 (empty net)
    
    int awaySkaters = int.Parse(code.Substring(1, 1));
    int homeSkaters = int.Parse(code.Substring(2, 1));
    
    return $"{awaySkaters}v{homeSkaters}";
    }
}

public class NhlPeriodDescriptor
{
    [JsonPropertyName("number")]
    public int Number { get; set; }

    [JsonPropertyName("periodType")]
    public string? PeriodType { get; set; }
}

public class NhlPlayDetails
{
    [JsonPropertyName("xCoord")]
    public int? XCoord { get; set; }

    [JsonPropertyName("yCoord")]
    public int? YCoord { get; set; }

    [JsonPropertyName("zoneCode")]
    public string? ZoneCode { get; set; }

    [JsonPropertyName("shotType")]
    public string? ShotType { get; set; }

    [JsonPropertyName("eventOwnerTeamId")]
    public int? EventOwnerTeamId { get; set; }

    [JsonPropertyName("reason")]
    public string? Reason { get; set; }

    [JsonPropertyName("winningPlayerId")]
    public int? WinningPlayerId { get; set; }

    [JsonPropertyName("losingPlayerId")]
    public int? LosingPlayerId { get; set; }

    [JsonPropertyName("scoringPlayerId")]
    public int? ScoringPlayerId { get; set; }

    [JsonPropertyName("shootingPlayerId")]
    public int? ShootingPlayerId { get; set; }

    [JsonPropertyName("goalieInNetId")]
    public int? GoalieInNetId { get; set; }

    [JsonPropertyName("hittingPlayerId")]
    public int? HittingPlayerId { get; set; }

    [JsonPropertyName("hitteePlayerId")]
    public int? HitteePlayerId { get; set; }

    [JsonPropertyName("committedByPlayerId")]
    public int? CommittedByPlayerId { get; set; }

    [JsonPropertyName("drawnByPlayerId")]
    public int? DrawnByPlayerId { get; set; }

    [JsonPropertyName("blockingPlayerId")]
    public int? BlockingPlayerId { get; set; }

    [JsonPropertyName("playerId")]
    public int? PlayerId { get; set; }

    [JsonPropertyName("descKey")]
    public string? DescKey { get; set; }

    [JsonPropertyName("duration")]
    public int? Duration { get; set; }

    [JsonPropertyName("typeCode")]
    public string? TypeCode { get; set; }

    [JsonPropertyName("assist1PlayerId")]
    public int? Assist1PlayerId { get; set; }

    [JsonPropertyName("assist2PlayerId")]
    public int? Assist2PlayerId { get; set; }

    [JsonPropertyName("awaySOG")]
    public int? AwaySOG { get; set; }

    [JsonPropertyName("homeSOG")]
    public int? HomeSOG { get; set; }

    [JsonPropertyName("awayScore")]
    public int? AwayScore { get; set; }

    [JsonPropertyName("homeScore")]
    public int? HomeScore { get; set; }

    [JsonPropertyName("scoringPlayerTotal")]
    public int? ScoringPlayerTotal { get; set; }

    [JsonPropertyName("assist1PlayerTotal")]
    public int? Assist1PlayerTotal { get; set; }

    [JsonPropertyName("assist2PlayerTotal")]
    public int? Assist2PlayerTotal { get; set; }
}

public class NhlRosters
{
    [JsonPropertyName("home")]
    public List<NhlRosterPlayer>? Home { get; set; }

    [JsonPropertyName("away")]
    public List<NhlRosterPlayer>? Away { get; set; }
}

public class NhlRosterPlayer
{
    [JsonPropertyName("playerId")]
    public int PlayerId { get; set; }

    [JsonPropertyName("firstName")]
    public NhlLocalizedName? FirstName { get; set; }

    [JsonPropertyName("lastName")]
    public NhlLocalizedName? LastName { get; set; }

    [JsonPropertyName("positionCode")]
    public string? PositionCode { get; set; }
    [JsonPropertyName("teamId")]
public int TeamId { get; set; }
    public string FullName
    {
        get
        {
            var first = FirstName?.Default ?? "";
            var last = LastName?.Default ?? "";
            return $"{first} {last}".Trim();
        }
    }
}