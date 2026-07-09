import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/design_system/design_system.dart';
import '../../../../core/widgets/async_value_view.dart';
import '../controllers/booking_flow_controller.dart';
import '../providers/booking_providers.dart';
import '../widgets/booking_card.dart';
import '../widgets/booking_timeline_sheet.dart';

/// Customer booking history (upcoming + past). Tap a booking to see its
/// lifecycle timeline; cancel from the card while it is still cancellable.
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
            ? const AppEmptyState(
                icon: Icons.event_note_outlined,
                title: 'No bookings yet',
                message: 'Book your first appointment from the Discover tab.',
              )
            : ListView.separated(
                padding: const EdgeInsets.all(AppSpacing.xl),
                itemCount: items.length,
                separatorBuilder: (_, __) => AppSpacing.gapMd,
                itemBuilder: (context, index) {
                  final booking = items[index];
                  return BookingCard(
                    booking: booking,
                    onTap: () => showBookingTimelineSheet(context, booking),
                    trailing: booking.isCancellableByCustomer
                        ? Align(
                            alignment: Alignment.centerRight,
                            child: AppButton(
                              label: 'Cancel',
                              variant: AppButtonVariant.danger,
                              size: AppButtonSize.small,
                              expand: false,
                              onPressed: () =>
                                  _confirmCancel(context, ref, booking.id),
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
