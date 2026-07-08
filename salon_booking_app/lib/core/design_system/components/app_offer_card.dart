import 'package:flutter/material.dart';

import '../tokens/app_colors.dart';
import '../tokens/app_radius.dart';
import '../tokens/app_shadows.dart';
import '../tokens/app_spacing.dart';
import '../tokens/app_typography.dart';

/// "Hot deal" carousel card: violet gradient ground, gold discount badge.
/// The one deliberately loud component in the system — everything around
/// it stays quiet so it reads as the highlight.
class AppOfferCard extends StatelessWidget {
  const AppOfferCard({
    super.key,
    required this.discountLabel,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.untilLabel,
    this.width = 260,
  });

  /// "-30%"
  final String discountLabel;
  final String title;

  /// Business name.
  final String subtitle;

  /// "until 6:00 PM" / "daily until 6:00 PM"
  final String? untilLabel;
  final VoidCallback onTap;
  final double width;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: AppRadius.cardAll,
          child: Ink(
            padding: const EdgeInsets.all(AppSpacing.lg - 2),
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [AppColors.primary, AppColors.primaryDark],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: AppRadius.cardAll,
              boxShadow: AppShadows.soft,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.sm,
                    vertical: 3,
                  ),
                  decoration: const BoxDecoration(
                    color: AppColors.accent,
                    borderRadius: AppRadius.badgeAll,
                  ),
                  child: Text(
                    discountLabel,
                    style: AppTypography.bodyStrong.copyWith(
                      fontWeight: FontWeight.w800,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ),
                const SizedBox(height: AppSpacing.sm + 2),
                Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTypography.subtitle.copyWith(
                    color: AppColors.textOnPrimary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  subtitle,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTypography.caption.copyWith(
                    fontSize: 13,
                    color: Colors.white70,
                  ),
                ),
                if (untilLabel != null) ...[
                  const SizedBox(height: AppSpacing.sm),
                  Row(
                    children: [
                      const Icon(
                        Icons.schedule_rounded,
                        size: 14,
                        color: Colors.white70,
                      ),
                      const SizedBox(width: AppSpacing.xs),
                      Text(
                        untilLabel!,
                        style: AppTypography.caption
                            .copyWith(color: Colors.white70),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
