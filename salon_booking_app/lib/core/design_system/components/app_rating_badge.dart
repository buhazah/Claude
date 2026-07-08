import 'package:flutter/material.dart';

import '../tokens/app_colors.dart';
import '../tokens/app_typography.dart';

/// Compact star + score badge (cards, detail headers).
///
/// One decimal, always ("4.0", not "4") — trust signals must look measured.
class AppRatingBadge extends StatelessWidget {
  const AppRatingBadge({
    super.key,
    required this.rating,
    this.count,
    this.compact = false,
  });

  final double rating;
  final int? count;

  /// Slightly smaller star/text (dense list rows).
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final starSize = compact ? 15.0 : 18.0;
    final scoreStyle = AppTypography.bodyStrong.copyWith(
      fontSize: compact ? 12 : 14,
      fontFeatures: AppTypography.tabularFigures,
    );

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.star_rounded, size: starSize, color: AppColors.rating),
        const SizedBox(width: 2),
        Text(rating.toStringAsFixed(1), style: scoreStyle),
        if (count != null) ...[
          const SizedBox(width: 4),
          Text(
            '($count)',
            style: AppTypography.caption.copyWith(
              fontSize: compact ? 11 : 12,
            ),
          ),
        ],
      ],
    );
  }
}
