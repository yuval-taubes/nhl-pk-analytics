using System.Text.Json;
using System.Text.Json.Serialization;

namespace NhlPkIngest.Models;

public class NhlShiftChartResponse
{
    [JsonPropertyName("data")]
    public List<NhlShiftChartRow>? Data { get; set; }
}

public class NhlShiftChartRow
{
    [JsonPropertyName("id")]
    [JsonConverter(typeof(NullIntAsZeroConverter))]
    public int Id { get; set; }

    [JsonPropertyName("duration")]
    public string? Duration { get; set; }

    [JsonPropertyName("endTime")]
    public string? EndTime { get; set; }

    [JsonPropertyName("firstName")]
    public string? FirstName { get; set; }

    [JsonPropertyName("gameId")]
    public int GameId { get; set; }

    [JsonPropertyName("lastName")]
    public string? LastName { get; set; }

    [JsonPropertyName("period")]
    public int Period { get; set; }

    [JsonPropertyName("playerId")]
    [JsonConverter(typeof(NullIntAsZeroConverter))]
    public int PlayerId { get; set; }

    [JsonPropertyName("shiftNumber")]
    public int ShiftNumber { get; set; }

    [JsonPropertyName("startTime")]
    public string? StartTime { get; set; }

    [JsonPropertyName("teamAbbrev")]
    public string? TeamAbbrev { get; set; }

    [JsonPropertyName("teamId")]
    [JsonConverter(typeof(NullIntAsZeroConverter))]
    public int TeamId { get; set; }

    [JsonPropertyName("teamName")]
    public string? TeamName { get; set; }
}

public sealed class NullIntAsZeroConverter : JsonConverter<int>
{
    public override int Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
        => reader.TokenType == JsonTokenType.Null ? 0 : reader.GetInt32();

    public override void Write(Utf8JsonWriter writer, int value, JsonSerializerOptions options)
        => writer.WriteNumberValue(value);
}
