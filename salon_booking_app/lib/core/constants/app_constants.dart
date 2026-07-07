/// App-wide, non-themable constants.
abstract final class AppConstants {
  static const String appName = 'Serene';
  static const String currencySymbol = 'AED';

  /// Default map center when device location is unavailable (Downtown Dubai).
  /// Swap for a per-city config document when expanding to new cities.
  static const double defaultLatitude = 25.1972;
  static const double defaultLongitude = 55.2744;

  /// Booking slots are generated on this grid (minutes).
  static const int slotGridMinutes = 30;

  /// How many days ahead a customer can book.
  static const int bookingHorizonDays = 14;

  /// Price filter bounds (AED) used by the discovery filter sheet.
  static const double minFilterPrice = 0;
  static const double maxFilterPrice = 1000;
}
