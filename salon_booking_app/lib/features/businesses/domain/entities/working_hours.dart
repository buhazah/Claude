/// Opening hours for one weekday, minutes-from-midnight resolution.
class DayHours {
  const DayHours({
    required this.closed,
    required this.openMinutes,
    required this.closeMinutes,
  });

  /// Sensible default for new businesses: 10:00–22:00.
  const DayHours.standard()
      : closed = false,
        openMinutes = 10 * 60,
        closeMinutes = 22 * 60;

  const DayHours.dayOff()
      : closed = true,
        openMinutes = 0,
        closeMinutes = 0;

  final bool closed;
  final int openMinutes;
  final int closeMinutes;

  DayHours copyWith({bool? closed, int? openMinutes, int? closeMinutes}) =>
      DayHours(
        closed: closed ?? this.closed,
        openMinutes: openMinutes ?? this.openMinutes,
        closeMinutes: closeMinutes ?? this.closeMinutes,
      );
}

/// Weekly schedule keyed by [DateTime.weekday] (1 = Monday … 7 = Sunday).
class WeeklyHours {
  const WeeklyHours(this._days);

  /// Open every day with [DayHours.standard].
  factory WeeklyHours.standard() => WeeklyHours({
        for (var day = DateTime.monday; day <= DateTime.sunday; day++)
          day: const DayHours.standard(),
      });

  final Map<int, DayHours> _days;

  DayHours forWeekday(int weekday) =>
      _days[weekday] ?? const DayHours.dayOff();

  WeeklyHours updating(int weekday, DayHours hours) =>
      WeeklyHours({..._days, weekday: hours});

  Map<int, DayHours> get days => Map.unmodifiable(_days);
}
