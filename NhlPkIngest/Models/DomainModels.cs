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
