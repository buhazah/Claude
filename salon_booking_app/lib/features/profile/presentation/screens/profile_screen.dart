import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/router/route_names.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../auth/presentation/controllers/auth_controller.dart';
import '../../../auth/presentation/providers/auth_providers.dart';

/// Customer profile: identity, shortcuts, sign out.
class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider).valueOrNull;

    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Card(
            child: ListTile(
              leading: CircleAvatar(
                backgroundColor: AppColors.primary.withValues(alpha: 0.12),
                child: const Icon(Icons.person_rounded,
                    color: AppColors.primary),
              ),
              title: Text(
                user?.name.isNotEmpty == true ? user!.name : 'Guest',
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              subtitle: Text(
                user == null
                    ? ''
                    : user.phone.isNotEmpty
                        ? user.phone
                        : user.email,
              ),
            ),
          ),
          const SizedBox(height: 16),
          Card(
            child: Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.event_note_outlined),
                  title: const Text('Booking history'),
                  trailing: const Icon(Icons.chevron_right_rounded),
                  onTap: () => context.go(RouteNames.myBookings),
                ),
                const Divider(height: 1),
                const ListTile(
                  leading: Icon(Icons.notifications_outlined),
                  title: Text('Notifications'),
                  subtitle: Text('Coming soon'),
                  enabled: false,
                ),
                const Divider(height: 1),
                const ListTile(
                  leading: Icon(Icons.payment_outlined),
                  title: Text('Payment methods'),
                  subtitle: Text('Coming soon'),
                  enabled: false,
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Card(
            child: ListTile(
              leading: const Icon(Icons.logout_rounded,
                  color: AppColors.danger),
              title: const Text(
                'Sign out',
                style: TextStyle(color: AppColors.danger),
              ),
              onTap: () =>
                  ref.read(authControllerProvider.notifier).signOut(),
            ),
          ),
        ],
      ),
    );
  }
}
