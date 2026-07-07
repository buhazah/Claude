import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/widgets/async_value_view.dart';
import '../../../../core/widgets/empty_state.dart';
import '../controllers/booking_flow_controller.dart';
import '../providers/booking_providers.dart';
import '../widgets/booking_card.dart';

/// Customer booking history (upcoming + past) with cancellation.
class MyBookingsScreen extends ConsumerWidget {
  const MyBookingsScreen({super.key});

  Future<void> _confirmCancel(
    BuildContext context,
    WidgetRef ref,
    String bookingId,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancel booking?'),
        content: const Text('The salon will be notified.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Keep it'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Cancel booking'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await ref.read(bookingActionsProvider).cancel(bookingId);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final bookings = ref.watch(myBookingsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('My bookings')),
      body: AsyncValueView(
        value: bookings,
        onRetry: () => ref.invalidate(myBookingsProvider),
        data: (items) => items.isEmpty
            ? const EmptyState(
                icon: Icons.event_note_outlined,
                title: 'No bookings yet',
                message: 'Book your first appointment from the Discover tab.',
              )
            : ListView.separated(
                padding: const EdgeInsets.all(20),
                itemCount: items.length,
                separatorBuilder: (_, __) => const SizedBox(height: 12),
                itemBuilder: (context, index) {
                  final booking = items[index];
                  return BookingCard(
                    booking: booking,
                    trailing: booking.isCancellableByCustomer
                        ? Align(
                            alignment: Alignment.centerRight,
                            child: OutlinedButton(
                              style: OutlinedButton.styleFrom(
                                minimumSize: const Size(0, 40),
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 16),
                              ),
                              onPressed: () =>
                                  _confirmCancel(context, ref, booking.id),
                              child: const Text('Cancel'),
                            ),
                          )
                        : null,
                  );
                },
              ),
      ),
    );
  }
}
