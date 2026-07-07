/// Route paths in one place, so navigation calls never hardcode strings.
abstract final class RouteNames {
  // Auth / onboarding
  static const String splash = '/splash';
  static const String login = '/login';
  static const String emailLogin = '/login/email';
  static const String otp = '/otp';
  static const String roleSelection = '/onboarding/role';

  // Customer
  static const String home = '/home';
  static const String myBookings = '/bookings';
  static const String profile = '/profile';

  static String salonDetail(String salonId) => '/salon/$salonId';
  static String bookService(String salonId, String serviceId) =>
      '/salon/$salonId/book/$serviceId';

  // Owner
  static const String ownerDashboard = '/owner/dashboard';
  static const String ownerBookings = '/owner/bookings';
  static const String ownerServices = '/owner/services';
  static const String ownerOffers = '/owner/offers';
  static const String ownerAvailability = '/owner/availability';
}
