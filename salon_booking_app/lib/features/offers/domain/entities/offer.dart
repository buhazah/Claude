/// A time-boxed discount created by a salon owner.
class Offer {
  const Offer({
    required this.id,
    required this.salonId,
    required this.salonName,
    required this.title,
    required this.discountPercent,
    required this.startTime,
    required this.endTime,
    required this.active,
    required this.maxRedemptions,
    required this.redemptionCount,
    required this.createdAt,
  });

  final String id;
  final String salonId;

  /// Denormalized for the "Hot deals" cards (avoids N salon reads).
  final String salonName;
  final String title;
  final int discountPercent;
  final DateTime startTime;
  final DateTime endTime;

  /// Owner kill-switch, independent of the time window.
  final bool active;

  /// 0 = unlimited. Otherwise the deal closes after this many bookings.
  final int maxRedemptions;
  final int redemptionCount;
  final DateTime createdAt;

  bool get hasCapacity =>
      maxRedemptions == 0 || redemptionCount < maxRedemptions;

  bool isLiveAt(DateTime moment) =>
      active &&
      hasCapacity &&
      !moment.isBefore(startTime) &&
      moment.isBefore(endTime);
}
