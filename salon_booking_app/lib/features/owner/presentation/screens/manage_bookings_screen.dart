import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../core/widgets/async_value_view.dart';
import '../../../../core/widgets/empty_state.dart';
import '../../../booking/domain/entities/booking.dart';
import '../../../booking/presentation/providers/booking_providers.dart';
import '../../../booking/presentation/widgets/booking_card.dart';
import '../../../salons/presentation/providers/salon_providers.dart';
import '../providers/owner_providers.dart';

/// Owner booking management: pending inbox + day-by-day schedule.
class ManageBookingsScreen extends ConsumerStatefulWidget {
  const ManageBookingsScreen({super.key});

  @override
  ConsumerState<ManageBookingsScreen> createState() =>
      _ManageBookingsScreenState();
}

class _ManageBookingsScreenState extends ConsumerState<ManageBookingsScreen> {
  late DateTime _scheduleDay;

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _scheduleDay = DateTime(now.year, now.month, now.day);
  }

  @override
  Widget build(BuildContext context) {
    final salon = ref.watch(ownerSalonProvider).valueOrNull;
    if (salon == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Bookings'),
          bottom: const TabBar(
            tabs: [
              Tab(text: 'Requests'),
              Tab(text: 'Schedule'),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            // --- Pending requests ---
            _PendingTab(),

            // --- Schedule by day ---
            Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 12, 20, 4),
                  child: Row(
                    children: [
                      Text(
                        Formatters.day(_scheduleDay),
                        style: const TextStyle(
                            fontWeight: FontWeight.w700, fontSize: 16),
                      ),
                      const Spacer(),
                      IconButton(
                        icon: const Icon(Icons.chevron_left_rounded),
                        onPressed: () => setState(() => _scheduleDay =
                            _scheduleDay.subtract(const Duration(days: 1))),
                      ),
                      IconButton(
                        icon: const Icon(Icons.chevron_right_rounded),
                        onPressed: () => setState(() => _scheduleDay =
                            _scheduleDay.add(const Duration(days: 1))),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: Consumer(
                    builder: (context, ref, _) {
                      final bookings = ref.watch(salonDayBookingsProvider(
                          (salonId: salon.id, day: _scheduleDay)));
                      return AsyncValueView(
                        value: bookings,
                        data: (items) {
                          final visible = items
                              .where((b) =>
                                  b.status != BookingStatus.cancelled)
                              .toList();
                          if (visible.isEmpty) {
                            return const EmptyState(
                              icon: Icons.event_available_outlined,
                              title: 'Nothing booked this day',
                            );
                          }
                          return ListView.separated(
                            padding: const EdgeInsets.all(20),
                            itemCount: visible.length,
                            separatorBuilder: (_, __) =>
                                const SizedBox(height: 12),
                            itemBuilder: (context, index) {
                              final booking = visible[index];
                              return BookingCard(
                                booking: booking,
                                showCustomer: true,
                                trailing: booking.status ==
                                        BookingStatus.confirmed
                                    ? Align(
                                        alignment: Alignment.centerRight,
                                        child: TextButton.icon(
                                          icon: const Icon(
                                              Icons.task_alt_rounded,
                                              size: 18),
                                          label: const Text('Mark completed'),
                                          onPressed: () => ref
                                              .read(ownerActionsProvider)
                                              .completeBooking(booking.id),
                                        ),
                                      )
                                    : null,
                              );
                            },
                          );
                        },
                      );
                    },
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _PendingTab extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pending = ref.watch(ownerPendingBookingsProvider);
    final actions = ref.read(ownerActionsProvider);

    return AsyncValueView(
      value: pending,
      onRetry: () => ref.invalidate(ownerPendingBookingsProvider),
      data: (items) => items.isEmpty
          ? const EmptyState(
              icon: Icons.inbox_outlined,
              title: 'No pending requests',
              message: 'New booking requests appear here instantly.',
            )
          : ListView.separated(
              padding: const EdgeInsets.all(20),
              itemCount: items.length,
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemBuilder: (context, index) {
                final booking = items[index];
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
                          style: FilledButton.styleFrom(
                              minimumSize: const Size(0, 42)),
                          onPressed: () => actions.acceptBooking(booking.id),
                          child: const Text('Accept'),
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
    );
  }
}
