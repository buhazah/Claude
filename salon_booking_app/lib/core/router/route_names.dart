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

  static String businessDetail(String businessId) => '/business/$businessId';
  static String bookService(String businessId, String serviceId) =>
      '/business/$businessId/book/$serviceId';

  // Owner
  static const String ownerDashboard = '/owner/dashboard';
  static const String ownerBookings = '/owner/bookings';
  static const String ownerServices = '/owner/services';
  static const String ownerOffers = '/owner/offers';
  static const String ownerAvailability = '/owner/availability';
  static const String ownerNewBusiness = '/owner/business/new';
}
