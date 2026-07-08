import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/errors/error_text.dart';
import '../../../businesses/presentation/providers/business_providers.dart';
import 'business_setup_screen.dart';

/// Owner area scaffold. Gates on business existence: owners without a
/// business profile see the setup screen before the dashboard.
class OwnerShell extends ConsumerWidget {
  const OwnerShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final businessAsync = ref.watch(ownerBusinessProvider);

    return businessAsync.when(
      loading: () =>
          const Scaffold(body: Center(child: CircularProgressIndicator())),
      error: (error, _) => Scaffold(
        body: Center(child: Text(errorText(error))),
      ),
      data: (business) {
        if (business == null) return const BusinessSetupScreen();
        return Scaffold(
          body: navigationShell,
          bottomNavigationBar: BottomNavigationBar(
            currentIndex: navigationShell.currentIndex,
            onTap: (index) => navigationShell.goBranch(
              index,
              initialLocation: index == navigationShell.currentIndex,
            ),
            items: const [
              BottomNavigationBarItem(
                icon: Icon(Icons.dashboard_outlined),
                activeIcon: Icon(Icons.dashboard_rounded),
                label: 'Dashboard',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.event_note_outlined),
                activeIcon: Icon(Icons.event_note_rounded),
                label: 'Bookings',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.design_services_outlined),
                activeIcon: Icon(Icons.design_services_rounded),
                label: 'Services',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.local_offer_outlined),
                activeIcon: Icon(Icons.local_offer_rounded),
                label: 'Offers',
              ),
            ],
          ),
        );
      },
    );
  }
}
