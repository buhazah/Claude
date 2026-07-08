import 'package:flutter/material.dart';

import '../tokens/app_radius.dart';
import '../tokens/app_spacing.dart';
import '../tokens/app_typography.dart';
import 'app_button.dart';

/// A bookable service row: name, price (with optional struck original),
/// duration, and one action.
class AppServiceCard extends StatelessWidget {
  const AppServiceCard({
    super.key,
    required this.name,
    required this.priceLabel,
    this.originalPriceLabel,
    this.durationLabel,
    this.actionLabel,
    this.onAction,
    this.trailing,
  });

  final String name;
  final String priceLabel;

  /// Pre-discount price, rendered struck-through.
  final String? originalPriceLabel;
  final String? durationLabel;

  /// When set (with [onAction]), renders the action button.
  final String? actionLabel;
  final VoidCallback? onAction;

  /// Custom trailing widget (owner edit/delete icons); overrides the
  /// action button.
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Card(
      shape: const RoundedRectangleBorder(borderRadius: AppRadius.cardAll),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.lg - 2,
          vertical: AppSpacing.md - 2,
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(name, style: AppTypography.bodyStrong),
                  const SizedBox(height: AppSpacing.xs),
                  Row(
                    children: [
                      Text(priceLabel, style: AppTypography.priceSmall),
                      if (originalPriceLabel != null) ...[
                        const SizedBox(width: AppSpacing.sm - 2),
                        Text(
                          originalPriceLabel!,
                          style: AppTypography.priceStruck,
                        ),
                      ],
                      if (durationLabel != null) ...[
                        const SizedBox(width: AppSpacing.sm),
                        Text(
                          '· $durationLabel',
                          style: AppTypography.caption.copyWith(fontSize: 13),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
            ),
            if (trailing != null)
              trailing!
            else if (actionLabel != null)
              AppButton(
                label: actionLabel!,
                onPressed: onAction,
                size: AppButtonSize.small,
                expand: false,
              ),
          ],
        ),
      ),
    );
  }
}
