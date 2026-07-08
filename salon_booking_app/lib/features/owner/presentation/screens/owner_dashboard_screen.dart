import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/router/route_names.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../core/utils/money.dart';
import '../../../../core/widgets/section_header.dart';
import '../../../auth/presentation/controllers/auth_controller.dart';
import '../../../booking/domain/entities/booking.dart';
import '../../../booking/presentation/widgets/booking_card.dart';
import '../../../booking/presentation/widgets/pending_booking_actions.dart';
import '../../../businesses/domain/entities/business.dart';
import '../../../businesses/presentation/providers/business_providers.dart';
import '../providers/owner_providers.dart';

/// Dashboard home: today's schedule, pending requests, revenue overview.
class OwnerDashboardScreen extends ConsumerWidget {
  const OwnerDashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final business = ref.watch(ownerBusinessProvider).valueOrNull;
    final businesses = ref.watch(ownerBusinessesProvider).valueOrNull ?? [];
    final today = ref.watch(ownerTodayBookingsProvider).valueOrNull ??
        const <Booking>[];
    final pending = ref.watch(ownerPendingBookingsProvider).valueOrNull ??
        const <Booking>[];

    // Simple revenue snapshot: confirmed + completed bookings today.
    final todayRevenue = today
        .where((b) =>
            b.status == BookingStatus.confirmed ||
            b.status == BookingStatus.completed)
        .fold<Money>(const Money.zero(), (sum, b) => sum + b.price);
    final activeToday = today.where((b) => b.status.blocksSlot).toList();

    return Scaffold(
      appBar: AppBar(
        title: businesses.length > 1
            ? _BusinessSwitcher(businesses: businesses)
            : Text(business?.name ?? 'Dashboard'),
        actions: [
          PopupMenuButton<String>(
            onSelected: (action) {
              switch (action) {
                case 'availability':
                  context.push(RouteNames.ownerAvailability);
                case 'add-branch':
                  context.push(RouteNames.ownerNewBusiness);
                case 'sign-out':
                  ref.read(authControllerProvider.notifier).signOut();
              }
            },
            itemBuilder: (context) => const [
              PopupMenuItem(
                value: 'availability',
                child: ListTile(
                  leading: Icon(Icons.schedule_rounded),
                  title: Text('Hours & availability'),
                  contentPadding: EdgeInsets.zero,
                ),
              ),
              PopupMenuItem(
                value: 'add-branch',
                child: ListTile(
                  leading: Icon(Icons.add_business_outlined),
                  title: Text('Add another branch'),
                  contentPadding: EdgeInsets.zero,
                ),
              ),
              PopupMenuItem(
                value: 'sign-out',
                child: ListTile(
                  leading: Icon(Icons.logout_rounded),
                  title: Text('Sign out'),
                  contentPadding: EdgeInsets.zero,
                ),
              ),
            ],
          ),
        ],
      ),
      body: ListView(
        children: [
          if (business != null && !business.approved)
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.warning.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.hourglass_top_rounded,
                        color: AppColors.warning),
                    SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Listing under review — customers can\'t see it '
                        'yet. You can set everything up in the meantime.',
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                    ),
                  ],
                ),
              ),
            ),
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
                    BookingCard(
                      booking: booking,
                      showCustomer: true,
                      trailing: PendingBookingActions(
                        onAccept: () => ref
                            .read(ownerActionsProvider)
                            .acceptBooking(booking.id),
                        onReject: () => ref
                            .read(ownerActionsProvider)
                            .rejectBooking(booking.id),
                      ),
                    ),
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

/// Branch dropdown for owners with more than one business.
class _BusinessSwitcher extends ConsumerWidget {
  const _BusinessSwitcher({required this.businesses});

  final List<Business> businesses;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final current = ref.watch(ownerBusinessProvider).valueOrNull;
    return DropdownButtonHideUnderline(
      child: DropdownButton<String>(
        value: current?.id,
        isExpanded: true,
        style: const TextStyle(
          color: AppColors.textPrimary,
          fontSize: 20,
          fontWeight: FontWeight.w700,
        ),
        items: [
          for (final business in businesses)
            DropdownMenuItem<String>(
              value: business.id,
              child: Text(business.name, overflow: TextOverflow.ellipsis),
            ),
        ],
        onChanged: (id) =>
            ref.read(selectedBusinessIdProvider.notifier).select(id),
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
