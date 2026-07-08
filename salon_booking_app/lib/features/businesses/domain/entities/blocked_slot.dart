import '../../../booking/domain/entities/time_range.dart';

/// A time range the owner has manually blocked. Blocks the entire business
/// (all capacity), unlike busy slots which consume one resource each.
///
/// Deliberately carries no free-text note: this document is publicly
/// readable (customers need it to compute availability), so nothing
/// private may live on it.
class BlockedSlot {
  const BlockedSlot({
    required this.id,
    required this.start,
    required this.end,
  });

  final String id;
  final DateTime start;
  final DateTime end;

  TimeRange get range => TimeRange(start: start, end: end);
}
