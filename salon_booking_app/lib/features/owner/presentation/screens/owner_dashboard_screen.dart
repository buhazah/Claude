import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/router/route_names.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../core/widgets/section_header.dart';
import '../../../auth/presentation/controllers/auth_controller.dart';
import '../../../booking/domain/entities/booking.dart';
import '../../../booking/presentation/widgets/booking_card.dart';
import '../../../salons/presentation/providers/salon_providers.dart';
import '../providers/owner_providers.dart';

/// Dashboard home: today's schedule, pending requests, revenue overview.
class OwnerDashboardScreen extends ConsumerWidget {
  const OwnerDashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final salon = ref.watch(ownerSalonProvider).valueOrNull;
    final today = ref.watch(ownerTodayBookingsProvider).valueOrNull ??
        const <Booking>[];
    final pending = ref.watch(ownerPendingBookingsProvider).valueOrNull ??
        const <Booking>[];

    // Simple revenue snapshot: confirmed + completed bookings today.
    final todayRevenue = today
        .where((b) =>
            b.status == BookingStatus.confirmed ||
            b.status == BookingStatus.completed)
        .fold<double>(0, (sum, b) => sum + b.price);
    final activeToday =
        today.where((b) => b.status.blocksSlot).toList();

    return Scaffold(
      appBar: AppBar(
        title: Text(salon?.name ?? 'Dashboard'),
        actions: [
          IconButton(
            tooltip: 'Working hours & blocked slots',
            icon: const Icon(Icons.schedule_rounded),
            onPressed: () => context.push(RouteNames.ownerAvailability),
          ),
          IconButton(
            tooltip: 'Sign out',
            icon: const Icon(Icons.logout_rounded),
            onPressed: () =>
                ref.read(authControllerProvider.notifier).signOut(),
          ),
        ],
      ),
      body: ListView(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
            child: Row(
              children: [
                _StatCard(
                  label: "Today's bookings",
                  value: '${activeToday.length}',
                  icon: Icons.event_available_rounded,
                  color: AppColors.primary,
                ),
                const SizedBox(width: 12),
                _StatCard(
                  label: 'Pending requests',
                  value: '${pending.length}',
                  icon: Icons.hourglass_top_rounded,
                  color: AppColors.warning,
                ),
                const SizedBox(width: 12),
                _StatCard(
                  label: 'Revenue today',
                  value: Formatters.price(todayRevenue),
                  icon: Icons.payments_rounded,
                  color: AppColors.success,
                ),
              ],
            ),
          ),
          if (pending.isNotEmpty) ...[
            SectionHeader(
              title: 'Pending requests',
              actionLabel: 'See all',
              onAction: () => context.go(RouteNames.ownerBookings),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Column(
                children: [
                  for (final booking in pending.take(3)) ...[
                    _PendingBookingCard(booking: booking),
                    const SizedBox(height: 12),
                  ],
                ],
              ),
            ),
          ],
          const SectionHeader(title: "Today's schedule"),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
            child: activeToday.isEmpty
                ? const Card(
                    child: Padding(
                      padding: EdgeInsets.all(20),
                      child: Text(
                        'No appointments today yet.',
                        style: TextStyle(color: AppColors.textSecondary),
                      ),
                    ),
                  )
                : Column(
                    children: [
                      for (final booking in activeToday) ...[
                        BookingCard(booking: booking, showCustomer: true),
                        const SizedBox(height: 12),
                      ],
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
  });

  final String label;
  final String value;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, color: color, size: 22),
              const SizedBox(height: 8),
              FittedBox(
                child: Text(
                  value,
                  style: const TextStyle(
                    fontWeight: FontWeight.w800,
                    fontSize: 18,
                  ),
                ),
              ),
              const SizedBox(height: 2),
              Text(
                label,
                style: const TextStyle(
                  color: AppColors.textSecondary,
                  fontSize: 11,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Pending card with inline accept/reject actions.
class _PendingBookingCard extends ConsumerWidget {
  const _PendingBookingCard({required this.booking});

  final Booking booking;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final actions = ref.read(ownerActionsProvider);
    return BookingCard(
      booking: booking,
      showCustomer: true,
      trailing: Row(
        children: [
          Expanded(
            child: OutlinedButton(
              style: OutlinedButton.styleFrom(
                minimumSize: const Size(0, 42),
                foregroundColor: AppColors.danger,
              ),
              onPressed: () => actions.rejectBooking(booking.id),
              child: const Text('Reject'),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: FilledButton(
              style: FilledButton.styleFrom(minimumSize: const Size(0, 42)),
              onPressed: () => actions.acceptBooking(booking.id),
              child: const Text('Accept'),
            ),
          ),
        ],
      ),
    );
  }
}
