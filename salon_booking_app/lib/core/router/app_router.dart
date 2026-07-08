import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/auth/presentation/providers/auth_providers.dart';
import '../../features/auth/presentation/screens/email_login_screen.dart';
import '../../features/auth/presentation/screens/login_screen.dart';
import '../../features/auth/presentation/screens/otp_screen.dart';
import '../../features/auth/presentation/screens/role_selection_screen.dart';
import '../../features/auth/presentation/screens/splash_screen.dart';
import '../../features/booking/presentation/screens/book_service_screen.dart';
import '../../features/booking/presentation/screens/my_bookings_screen.dart';
import '../../features/businesses/presentation/screens/business_detail_screen.dart';
import '../../features/home/presentation/screens/customer_shell.dart';
import '../../features/home/presentation/screens/home_screen.dart';
import '../../features/owner/presentation/screens/availability_screen.dart';
import '../../features/owner/presentation/screens/business_setup_screen.dart';
import '../../features/owner/presentation/screens/manage_bookings_screen.dart';
import '../../features/owner/presentation/screens/manage_offers_screen.dart';
import '../../features/owner/presentation/screens/manage_services_screen.dart';
import '../../features/owner/presentation/screens/owner_dashboard_screen.dart';
import '../../features/owner/presentation/screens/owner_shell.dart';
import '../../features/profile/presentation/screens/profile_screen.dart';
import 'route_names.dart';

/// Role-based router.
///
/// Redirect rules (evaluated on every auth/profile change):
///   signed out            → /login
///   signed in, no role    → role selection (first-run onboarding)
///   role == owner         → /owner/* (dashboard shell)
///   role == customer      → customer shell (/home, /bookings, /profile)
final appRouterProvider = Provider<GoRouter>((ref) {
  // Bump a Listenable whenever the auth/profile stream emits so GoRouter
  // re-evaluates redirects without rebuilding the whole router.
  final refresh = ValueNotifier<int>(0);
  ref.onDispose(refresh.dispose);
  ref.listen(currentUserProvider, (_, __) => refresh.value++);

  const authRoutes = {
    RouteNames.login,
    RouteNames.emailLogin,
    RouteNames.otp,
  };

  final router = GoRouter(
    initialLocation: RouteNames.splash,
    refreshListenable: refresh,
    redirect: (context, state) {
      final auth = ref.read(currentUserProvider);
      final location = state.matchedLocation;
      final onAuthRoute = authRoutes.contains(location);

      if (auth.isLoading) {
        return location == RouteNames.splash ? null : RouteNames.splash;
      }

      final user = auth.valueOrNull;
      if (user == null) {
        return onAuthRoute ? null : RouteNames.login;
      }
      if (user.needsRoleSelection) {
        return location == RouteNames.roleSelection
            ? null
            : RouteNames.roleSelection;
      }
      if (user.isOwner) {
        return location.startsWith('/owner')
            ? null
            : RouteNames.ownerDashboard;
      }
      // Customer: keep them out of auth/onboarding/owner areas.
      final mustLeave = onAuthRoute ||
          location == RouteNames.splash ||
          location == RouteNames.roleSelection ||
          location.startsWith('/owner');
      return mustLeave ? RouteNames.home : null;
    },
    routes: [
      GoRoute(
        path: RouteNames.splash,
        builder: (context, state) => const SplashScreen(),
      ),
      GoRoute(
        path: RouteNames.login,
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: RouteNames.emailLogin,
        builder: (context, state) => const EmailLoginScreen(),
      ),
      GoRoute(
        path: RouteNames.otp,
        builder: (context, state) => const OtpScreen(),
      ),
      GoRoute(
        path: RouteNames.roleSelection,
        builder: (context, state) => const RoleSelectionScreen(),
      ),

      // --- Customer area (bottom-nav shell) ---
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) =>
            CustomerShell(navigationShell: navigationShell),
        branches: [
          StatefulShellBranch(routes: [
            GoRoute(
              path: RouteNames.home,
              builder: (context, state) => const HomeScreen(),
            ),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(
              path: RouteNames.myBookings,
              builder: (context, state) => const MyBookingsScreen(),
            ),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(
              path: RouteNames.profile,
              builder: (context, state) => const ProfileScreen(),
            ),
          ]),
        ],
      ),
      GoRoute(
        path: '/business/:businessId',
        builder: (context, state) => BusinessDetailScreen(
          businessId: state.pathParameters['businessId']!,
        ),
      ),
      GoRoute(
        path: '/business/:businessId/book/:serviceId',
        builder: (context, state) => BookServiceScreen(
          businessId: state.pathParameters['businessId']!,
          serviceId: state.pathParameters['serviceId']!,
        ),
      ),

      // --- Owner area (dashboard shell) ---
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) =>
            OwnerShell(navigationShell: navigationShell),
        branches: [
          StatefulShellBranch(routes: [
            GoRoute(
              path: RouteNames.ownerDashboard,
              builder: (context, state) => const OwnerDashboardScreen(),
            ),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(
              path: RouteNames.ownerBookings,
              builder: (context, state) => const ManageBookingsScreen(),
            ),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(
              path: RouteNames.ownerServices,
              builder: (context, state) => const ManageServicesScreen(),
            ),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(
              path: RouteNames.ownerOffers,
              builder: (context, state) => const ManageOffersScreen(),
            ),
          ]),
        ],
      ),
      GoRoute(
        path: RouteNames.ownerAvailability,
        builder: (context, state) => const AvailabilityScreen(),
      ),
      GoRoute(
        path: RouteNames.ownerNewBusiness,
        builder: (context, state) => const BusinessSetupScreen(),
      ),
    ],
  );
  ref.onDispose(router.dispose);
  return router;
});
