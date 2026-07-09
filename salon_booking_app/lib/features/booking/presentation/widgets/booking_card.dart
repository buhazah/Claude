import 'package:flutter/material.dart';

import '../../../../core/design_system/design_system.dart';
import '../../../../core/utils/formatters.dart';
import '../../domain/entities/booking.dart';

/// Booking summary card shared by the customer history and owner lists.
/// [trailing] hosts context-specific actions (cancel / accept / reject);
/// [onTap] (optional) opens a detail view.
class BookingCard extends StatelessWidget {
  const BookingCard({
    super.key,
    required this.booking,
    this.showCustomer = false,
    this.trailing,
    this.onTap,
  });

  final Booking booking;

  /// Owner views show who booked; customer views show the business instead.
  final bool showCustomer;
  final Widget? trailing;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final content = Padding(
      padding: AppSpacing.cardPadding,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(booking.serviceName, style: AppTypography.subtitle),
              ),
              _StatusChip(status: booking.status),
            ],
          ),
          AppSpacing.gapXs,
          Text(
            showCustomer
                ? booking.customerName.isEmpty
                    ? 'Customer'
                    : booking.customerName
                : booking.businessName,
            style: AppTypography.bodyMuted,
          ),
          AppSpacing.gapSm,
          Row(
            children: [
              const Icon(Icons.schedule_rounded,
                  size: 16, color: AppColors.textSecondary),
              const SizedBox(width: AppSpacing.xs),
              Expanded(
                child: Text(
                  '${Formatters.dayTime(booking.start)} · '
                  '${Formatters.duration(booking.durationMinutes)}',
                  style: AppTypography.caption.copyWith(fontSize: 13),
                ),
              ),
              if (booking.hasDiscount) ...[
                Text(
                  Formatters.price(booking.originalPrice),
                  style: AppTypography.priceStruck,
                ),
                const SizedBox(width: AppSpacing.sm - 2),
              ],
              Text(Formatters.price(booking.price),
                  style: AppTypography.priceSmall),
            ],
          ),
          if (trailing != null) ...[
            AppSpacing.gapMd,
            trailing!,
          ],
        ],
      ),
    );

    return Card(
      clipBehavior: Clip.antiAlias,
      child: onTap == null
          ? content
          : InkWell(onTap: onTap, child: content),
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
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm + 2,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: _color.withValues(alpha: 0.12),
        borderRadius: AppRadius.badgeAll,
      ),
      child: Text(
        status.label,
        style: AppTypography.caption.copyWith(
          color: _color,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
