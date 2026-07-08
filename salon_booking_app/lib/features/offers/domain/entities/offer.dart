/// A time-boxed discount created by a business owner.
///
/// Two time dimensions compose:
///  * validity period: [startTime, endTime) — the offer's lifetime;
///  * optional daily window: [dailyStartMinute, dailyEndMinute) minutes
///    from midnight — "3pm–6pm every day" style happy hours. Null = the
///    offer is live for its entire validity period.
class Offer {
  const Offer({
    required this.id,
    required this.businessId,
    required this.businessName,
    required this.title,
    required this.discountPercent,
    required this.startTime,
    required this.endTime,
    required this.active,
    required this.maxRedemptions,
    required this.redemptionCount,
    required this.createdAt,
    this.dailyStartMinute,
    this.dailyEndMinute,
  });

  final String id;
  final String businessId;

  /// Denormalized for the "Hot deals" cards (avoids N business reads).
  final String businessName;
  final String title;
  final int discountPercent;
  final DateTime startTime;
  final DateTime endTime;

  /// Owner kill-switch, independent of the time windows.
  final bool active;

  /// 0 = unlimited. Otherwise the deal closes after this many bookings.
  final int maxRedemptions;
  final int redemptionCount;
  final DateTime createdAt;

  /// Recurring daily window (minutes from midnight), both set or both null.
  final int? dailyStartMinute;
  final int? dailyEndMinute;

  bool get hasDailyWindow => dailyStartMinute != null && dailyEndMinute != null;

  bool get hasCapacity =>
      maxRedemptions == 0 || redemptionCount < maxRedemptions;

  bool isLiveAt(DateTime moment) {
    if (!active || !hasCapacity) return false;
    if (moment.isBefore(startTime) || !moment.isBefore(endTime)) return false;
    if (hasDailyWindow) {
      final minuteOfDay = moment.hour * 60 + moment.minute;
      if (minuteOfDay < dailyStartMinute! || minuteOfDay >= dailyEndMinute!) {
        return false;
      }
    }
    return true;
  }
}
