/// A half-open time range [start, end). The shared overlap primitive for
/// busy slots, blocked slots, and slot generation.
class TimeRange {
  const TimeRange({required this.start, required this.end});

  final DateTime start;
  final DateTime end;

  bool overlaps(DateTime otherStart, DateTime otherEnd) =>
      start.isBefore(otherEnd) && end.isAfter(otherStart);

  @override
  bool operator ==(Object other) =>
      other is TimeRange && other.start == start && other.end == end;

  @override
  int get hashCode => Object.hash(start, end);
}
