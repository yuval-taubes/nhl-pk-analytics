namespace NhlPkIngest.Models;

public class Team
{
    public int TeamId { get; set; }
    public string Name { get; set; } = "";
    public string Abbreviation { get; set; } = "";
}

public class Player
{
    public int PlayerId { get; set; }
    public string FullName { get; set; } = "";
    public string Position { get; set; } = "";
}

public class GamePlayer
{
    public int GameId { get; set; }
    public int PlayerId { get; set; }
    public int TeamId { get; set; }
}

public class Game
{
    public int GameId { get; set; }
    public string? Season { get; set; }
    public DateOnly GameDate { get; set; }
    public int HomeTeamId { get; set; }
    public int AwayTeamId { get; set; }
    public int HomeScore { get; set; }
    public int AwayScore { get; set; }
}

public class Event
{
    public int GameId { get; set; }
    public int EventIdx { get; set; }
    public int Period { get; set; }
    public int PeriodTimeSeconds { get; set; }
    public string? EventType { get; set; }
    public int? EventTeamId { get; set; }
    public int? X { get; set; }
    public int? Y { get; set; }
    public int? XNorm { get; set; }
    public int? YNorm { get; set; }
    public string? Zone { get; set; }
    public string? Strength { get; set; }
    public string? Description { get; set; }
    public int HomeSkaters { get; set; }
    public int AwaySkaters { get; set; }
}

public class Possession
{
    public int PossessionId { get; set; } // from SERIAL
    public int GameId { get; set; }
    public int TeamId { get; set; }
    public int StartEventId { get; set; }
    public int StartEventOriginalIdx { get; set; }
    public int EndEventId { get; set; }
    public int EndEventOriginalIdx { get; set; }
    public string? Strength { get; set; }
    public string? EntryType { get; set; }
    public int? EntryX { get; set; }
    public int? EntryY { get; set; }
    public string? StartZone { get; set; }
    public string? EndType { get; set; }
    public decimal DurationSeconds { get; set; }
    public int ShotCount { get; set; }
    public int GoalCount { get; set; }
    public decimal XgSum { get; set; }
}

public class Shot
{
    public int ShotId { get; set; }
    public int EventId { get; set; }
    public int OriginalEventIdx { get; set; }
    public int PossessionId { get; set; }
    public int ShooterId { get; set; }
    public int ShooterTeamId { get; set; } // internal use
    public int? X { get; set; }
    public int? Y { get; set; }
    public int? XNorm { get; set; }
    public int? YNorm { get; set; }
    public string? ShotType { get; set; }
    public bool IsGoal { get; set; }
    public decimal? Xg { get; set; }
}

public class EventPlayer
{
    public int EventId { get; set; }
    public int PlayerId { get; set; }
    public int OriginalEventIdx { get; set; }
    public int TeamId { get; set; }
    public bool IsHome { get; set; }
}
public class GameShift
{
    public int SourceShiftId { get; set; }
    public int GameId { get; set; }
    public int PlayerId { get; set; }
    public int TeamId { get; set; }
    public bool IsHome { get; set; }
    public int Period { get; set; }
    public int ShiftNumber { get; set; }
    public string? StartTime { get; set; }
    public string? EndTime { get; set; }
    public string? Duration { get; set; }
    public int StartSeconds { get; set; }
    public int EndSeconds { get; set; }
    public int StartGameSeconds { get; set; }
    public int EndGameSeconds { get; set; }
    public decimal DurationSeconds { get; set; }
}

public class ShiftSourceResult
{
    public required string Status { get; init; }
    public required string EndpointUrl { get; init; }
    public List<NhlShiftChartRow> Rows { get; init; } = new();
    public int? HttpStatusCode { get; init; }
    public string? ErrorMessage { get; init; }
}

public class EventOnIcePlayer
{
    public int EventId { get; set; }
    public int PlayerId { get; set; }
    public int TeamId { get; set; }
    public bool IsHome { get; set; }
    public bool IsGoalie { get; set; }
    public bool IsSkater => !IsGoalie;
    public int OriginalEventIdx { get; set; }
}

public class EventManpower
{
    public int EventId { get; set; }
    public int OriginalEventIdx { get; set; }
    public int HomeSkatersShift { get; set; }
    public int AwaySkatersShift { get; set; }
    public int? HomeGoalieId { get; set; }
    public int? AwayGoalieId { get; set; }
    public bool HomeGoaliePulled { get; set; }
    public bool AwayGoaliePulled { get; set; }
    public string? StrengthStateShift { get; set; }
    public string? StrengthCodeShift { get; set; }
    public bool MatchesSituationCode { get; set; }
}
