import 'package:flutter/material.dart';

import '../../../../core/design_system/design_system.dart';
import '../../../../core/utils/formatters.dart';
import '../../domain/entities/booking.dart';

/// Booking-detail sheet: appointment summary + lifecycle timeline.
/// Maps a [Booking]'s status onto [AppBookingTimeline] steps.
Future<void> showBookingTimelineSheet(
  BuildContext context,
  Booking booking,
) {
  return showAppBottomSheet(
    context: context,
    title: booking.serviceName,
    builder: (context) => Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '${booking.businessName} · ${Formatters.dayTime(booking.start)}',
          style: AppTypography.bodyMuted,
        ),
        AppSpacing.gapXs,
        Row(
          children: [
            Text(Formatters.price(booking.price), style: AppTypography.price),
            if (booking.hasDiscount) ...[
              AppSpacing.gapSm,
              Text(
                Formatters.price(booking.originalPrice),
                style: AppTypography.priceStruck,
              ),
            ],
          ],
        ),
        AppSpacing.gapXl,
        AppBookingTimeline(steps: _steps(booking)),
        AppSpacing.gapMd,
      ],
    ),
  );
}

List<AppTimelineStep> _steps(Booking booking) {
  final requested = AppTimelineStep(
    title: 'Requested',
    subtitle: Formatters.dayTime(booking.createdAt),
    state: AppTimelineState.complete,
  );

  if (booking.status == BookingStatus.cancelled) {
    return [
      requested,
      const AppTimelineStep(
        title: 'Cancelled',
        state: AppTimelineState.cancelled,
      ),
    ];
  }

  final confirmedDone = booking.status == BookingStatus.confirmed ||
      booking.status == BookingStatus.completed;
  final completedDone = booking.status == BookingStatus.completed;

  return [
    requested,
    AppTimelineStep(
      title: 'Confirmed',
      subtitle: confirmedDone ? 'by the salon' : 'awaiting the salon',
      state: confirmedDone
          ? AppTimelineState.complete
          : AppTimelineState.active,
    ),
    AppTimelineStep(
      title: 'Completed',
      subtitle: Formatters.dayTime(booking.start),
      state: completedDone
          ? AppTimelineState.complete
          : AppTimelineState.upcoming,
    ),
  ];
}
