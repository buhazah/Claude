/// Single source of truth for Firestore collection / field names.
/// Keep in lockstep with `firebase/firestore.rules` and the indexes file.
///
/// Naming convention (see docs/CONVENTIONS.md): Firestore field names match
/// the domain entity property names exactly (e.g. `durationMinutes`,
/// `discountPercent`, `priceFils`) so there is no mapping drift.
abstract final class FirestoreCollections {
  static const String users = 'users';

  /// Generic marketplace businesses (salons today; spas, clinics, barbers
  /// tomorrow). The vertical lives in the `category` field, not the
  /// collection name.
  static const String businesses = 'businesses';
  static const String services = 'services';
  static const String bookings = 'bookings';
  static const String offers = 'offers';

  /// Subcollections of `businesses/{businessId}`.
  ///
  /// `resources`   — bookable capacity units (chairs / rooms / staff).
  /// `blockedSlots`— owner-blocked time ranges (block the whole business).
  /// `busySlots`   — privacy-minimized public projection of taken time
  ///                 ranges (start/end/bookingId only, no customer data),
  ///                 so customers can compute availability without read
  ///                 access to other people's booking documents.
  static const String resources = 'resources';
  static const String blockedSlots = 'blockedSlots';
  static const String busySlots = 'busySlots';
}
