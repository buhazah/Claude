import 'package:flutter/material.dart';

import '../tokens/app_colors.dart';
import '../tokens/app_motion.dart';
import '../tokens/app_radius.dart';
import '../tokens/app_spacing.dart';
import '../tokens/app_typography.dart';

/// Selectable filter/choice chip.
///
/// Selection is communicated by fill + text color + border, animated with
/// [AppMotion.fast] — never by size change (rows must not reflow when a
/// chip is tapped).
class AppFilterChip extends StatelessWidget {
  const AppFilterChip({
    super.key,
    required this.label,
    required this.selected,
    required this.onSelected,
    this.icon,
  });

  final String label;
  final bool selected;
  final ValueChanged<bool> onSelected;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final foreground =
        selected ? AppColors.primaryDark : AppColors.textPrimary;

    return Semantics(
      button: true,
      selected: selected,
      child: InkWell(
        onTap: () => onSelected(!selected),
        borderRadius: AppRadius.chipAll,
        child: AnimatedContainer(
          duration: AppMotion.fast,
          curve: AppMotion.standard,
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.lg,
            vertical: AppSpacing.sm + 2,
          ),
          decoration: BoxDecoration(
            color: selected ? AppColors.primarySubtle : AppColors.surface,
            borderRadius: AppRadius.chipAll,
            border: Border.all(
              color: selected ? AppColors.primary : AppColors.border,
              width: selected ? 1.5 : 1,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[
                Icon(icon, size: 16, color: foreground),
                const SizedBox(width: AppSpacing.xs + 2),
              ],
              Text(
                label,
                style: AppTypography.bodyStrong.copyWith(
                  fontSize: 13,
                  color: foreground,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
