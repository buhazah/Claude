import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/formatters.dart';
import '../../domain/entities/booking.dart';

/// Booking summary card shared by the customer history and owner lists.
/// [trailing] hosts context-specific actions (cancel / accept / reject).
class BookingCard extends StatelessWidget {
  const BookingCard({
    super.key,
    required this.booking,
    this.showCustomer = false,
    this.trailing,
  });

  final Booking booking;

  /// Owner views show who booked; customer views show the business instead.
  final bool showCustomer;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    booking.serviceName,
                    style: const TextStyle(
                        fontWeight: FontWeight.w700, fontSize: 15),
                  ),
                ),
                _StatusChip(status: booking.status),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              showCustomer
                  ? booking.customerName.isEmpty
                      ? 'Customer'
                      : booking.customerName
                  : booking.businessName,
              style: const TextStyle(color: AppColors.textSecondary),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                const Icon(Icons.schedule_rounded,
                    size: 16, color: AppColors.textSecondary),
                const SizedBox(width: 4),
                Text(
                  '${Formatters.dayTime(booking.start)} · '
                  '${Formatters.duration(booking.durationMinutes)}',
                  style: const TextStyle(
                      color: AppColors.textSecondary, fontSize: 13),
                ),
                const Spacer(),
                if (booking.hasDiscount) ...[
                  Text(
                    Formatters.price(booking.originalPrice),
                    style: const TextStyle(
                      color: AppColors.textSecondary,
                      decoration: TextDecoration.lineThrough,
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(width: 6),
                ],
                Text(
                  Formatters.price(booking.price),
                  style: const TextStyle(
                    color: AppColors.primary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
            if (trailing != null) ...[
              const SizedBox(height: 12),
              trailing!,
            ],
          ],
        ),
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.status});

  final BookingStatus status;

  Color get _color => switch (status) {
        BookingStatus.pending => AppColors.statusPending,
        BookingStatus.confirmed => AppColors.statusConfirmed,
        BookingStatus.cancelled => AppColors.statusCancelled,
        BookingStatus.completed => AppColors.statusCompleted,
      };

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: _color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        status.label,
        style: TextStyle(
          color: _color,
          fontSize: 12,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
