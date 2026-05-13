namespace NhlPkIngest.Models;

/// <summary>
/// Internal representation during processing before DB insert.
/// </summary>
public class ProcessedEvent
{
    public int OriginalEventIdx { get; set; }
    public int EventId { get; set; } // Filled after DB insert
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

    public Event ToEvent() => new Event
    {
        GameId = GameId,
        EventIdx = EventIdx,
        Period = Period,
        PeriodTimeSeconds = PeriodTimeSeconds,
        EventType = EventType,
        EventTeamId = EventTeamId,
        X = X,
        Y = Y,
        XNorm = XNorm,
        YNorm = YNorm,
        Zone = Zone,
        Strength = Strength,
        Description = Description,
        HomeSkaters = HomeSkaters,
        AwaySkaters = AwaySkaters
    };
}