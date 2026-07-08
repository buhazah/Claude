import 'package:flutter/material.dart';

import '../tokens/app_colors.dart';
import '../tokens/app_spacing.dart';
import '../tokens/app_typography.dart';

enum AppTimelineState { complete, active, upcoming, cancelled }

class AppTimelineStep {
  const AppTimelineStep({
    required this.title,
    this.subtitle,
    this.state = AppTimelineState.upcoming,
  });

  final String title;
  final String? subtitle;
  final AppTimelineState state;
}

/// Vertical booking-lifecycle timeline (Requested → Confirmed → Completed).
///
/// State is encoded in the node form, not just color: filled check =
/// complete, ringed dot = active, hollow dot = upcoming, cross = cancelled.
class AppBookingTimeline extends StatelessWidget {
  const AppBookingTimeline({super.key, required this.steps});

  final List<AppTimelineStep> steps;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var i = 0; i < steps.length; i++)
          _TimelineRow(
            step: steps[i],
            isLast: i == steps.length - 1,
          ),
      ],
    );
  }
}

class _TimelineRow extends StatelessWidget {
  const _TimelineRow({required this.step, required this.isLast});

  final AppTimelineStep step;
  final bool isLast;

  Color get _color => switch (step.state) {
        AppTimelineState.complete => AppColors.success,
        AppTimelineState.active => AppColors.primary,
        AppTimelineState.upcoming => AppColors.textTertiary,
        AppTimelineState.cancelled => AppColors.danger,
      };

  @override
  Widget build(BuildContext context) {
    final muted = step.state == AppTimelineState.upcoming;

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Column(
            children: [
              _Node(state: step.state, color: _color),
              if (!isLast)
                Expanded(
                  child: Container(
                    width: 2,
                    margin: const EdgeInsets.symmetric(vertical: 2),
                    decoration: BoxDecoration(
                      color: step.state == AppTimelineState.complete
                          ? AppColors.success.withValues(alpha: 0.4)
                          : AppColors.border,
                      borderRadius: BorderRadius.circular(1),
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(bottom: isLast ? 0 : AppSpacing.xl),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    step.title,
                    style: AppTypography.bodyStrong.copyWith(
                      color: muted
                          ? AppColors.textSecondary
                          : AppColors.textPrimary,
                    ),
                  ),
                  if (step.subtitle != null) ...[
                    const SizedBox(height: AppSpacing.xxs),
                    Text(step.subtitle!, style: AppTypography.caption),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Node extends StatelessWidget {
  const _Node({required this.state, required this.color});

  final AppTimelineState state;
  final Color color;

  static const double _size = 22;

  @override
  Widget build(BuildContext context) {
    return switch (state) {
      AppTimelineState.complete => Container(
          width: _size,
          height: _size,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          child: const Icon(
            Icons.check_rounded,
            size: 14,
            color: Colors.white,
          ),
        ),
      AppTimelineState.cancelled => Container(
          width: _size,
          height: _size,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          child: const Icon(
            Icons.close_rounded,
            size: 14,
            color: Colors.white,
          ),
        ),
      AppTimelineState.active => Container(
          width: _size,
          height: _size,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(color: color, width: 2),
          ),
          alignment: Alignment.center,
          child: Container(
            width: 10,
            height: 10,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
        ),
      AppTimelineState.upcoming => Container(
          width: _size,
          height: _size,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(color: AppColors.border, width: 2),
          ),
        ),
    };
  }
}
