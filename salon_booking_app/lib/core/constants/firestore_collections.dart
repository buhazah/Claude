/// Single source of truth for Firestore collection / field names.
/// Keep in lockstep with `firebase/firestore.rules` and the indexes file.
abstract final class FirestoreCollections {
  static const String users = 'users';
  static const String salons = 'salons';
  static const String services = 'services';
  static const String bookings = 'bookings';
  static const String offers = 'offers';

  /// Subcollection of `salons/{salonId}` holding owner-blocked time ranges.
  static const String blockedSlots = 'blockedSlots';
}
