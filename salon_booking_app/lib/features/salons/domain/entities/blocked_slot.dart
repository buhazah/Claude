/// A time range the owner has manually blocked (break, maintenance, walk-in).
class BlockedSlot {
  const BlockedSlot({
    required this.id,
    required this.start,
    required this.end,
    this.reason = '',
  });

  final String id;
  final DateTime start;
  final DateTime end;
  final String reason;

  bool overlaps(DateTime rangeStart, DateTime rangeEnd) =>
      start.isBefore(rangeEnd) && end.isAfter(rangeStart);
}
