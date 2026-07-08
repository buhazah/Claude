import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/router/app_router.dart';
import 'core/theme/app_theme.dart';

/// Root widget. Deliberately thin: theme + router only.
/// All app behavior lives in feature modules under `lib/features/`.
class SalonBookingApp extends ConsumerWidget {
  const SalonBookingApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(appRouterProvider);

    return MaterialApp.router(
      title: 'Serene — Salon Booking',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      // Pinned to light until the screen-migration phase removes direct
      // static-color references (docs/DESIGN_SYSTEM.md → "Dark mode").
      themeMode: ThemeMode.light,
      routerConfig: router,
    );
  }
}
