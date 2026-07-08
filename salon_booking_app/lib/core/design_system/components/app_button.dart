import 'package:flutter/material.dart';

import '../tokens/app_colors.dart';
import '../tokens/app_radius.dart';
import '../tokens/app_spacing.dart';
import '../tokens/app_typography.dart';

enum AppButtonVariant {
  /// Filled violet — the ONE primary action on a screen.
  primary,

  /// Outlined — secondary actions beside a primary.
  secondary,

  /// Text-only — tertiary/inline actions.
  ghost,

  /// Outlined red — destructive (cancel booking, delete).
  danger,
}

enum AppButtonSize { small, medium, large }

/// The system button. One widget, four variants, three sizes, built-in
/// loading state (spinner replaces the label and blocks taps).
///
/// Rules:
///  * One [AppButtonVariant.primary] per screen region.
///  * Destructive actions are [danger], never a red-tinted primary.
///  * Buttons never shrink below their size's height; full-width by default
///    for large, intrinsic for small/medium (override with [expand]).
class AppButton extends StatelessWidget {
  const AppButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.variant = AppButtonVariant.primary,
    this.size = AppButtonSize.large,
    this.loading = false,
    this.icon,
    this.expand,
  });

  final String label;
  final VoidCallback? onPressed;
  final AppButtonVariant variant;
  final AppButtonSize size;
  final bool loading;
  final IconData? icon;

  /// Defaults to true for [AppButtonSize.large], false otherwise.
  final bool? expand;

  double get _height => switch (size) {
        AppButtonSize.small => 40,
        AppButtonSize.medium => 46,
        AppButtonSize.large => 52,
      };

  double get _fontSize => switch (size) {
        AppButtonSize.small => 13,
        AppButtonSize.medium => 14,
        AppButtonSize.large => 16,
      };

  @override
  Widget build(BuildContext context) {
    final isExpanded = expand ?? (size == AppButtonSize.large);
    final effectiveOnPressed = loading ? null : onPressed;

    final child = loading
        ? SizedBox(
            height: _fontSize + 6,
            width: _fontSize + 6,
            child: const CircularProgressIndicator(strokeWidth: 2.5),
          )
        : icon == null
            ? Text(label)
            : Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(icon, size: _fontSize + 4),
                  const SizedBox(width: AppSpacing.sm),
                  Text(label),
                ],
              );

    final minimumSize = isExpanded
        ? Size.fromHeight(_height)
        : Size(_height * 2, _height);
    final padding = EdgeInsets.symmetric(
      horizontal: size == AppButtonSize.small ? AppSpacing.lg : AppSpacing.xl,
    );
    final textStyle = AppTypography.bodyStrong.copyWith(fontSize: _fontSize);
    const shape = RoundedRectangleBorder(borderRadius: AppRadius.controlAll);

    final button = switch (variant) {
      AppButtonVariant.primary => FilledButton(
          onPressed: effectiveOnPressed,
          style: FilledButton.styleFrom(
            minimumSize: minimumSize,
            padding: padding,
            shape: shape,
            textStyle: textStyle,
          ),
          child: child,
        ),
      AppButtonVariant.secondary => OutlinedButton(
          onPressed: effectiveOnPressed,
          style: OutlinedButton.styleFrom(
            minimumSize: minimumSize,
            padding: padding,
            shape: shape,
            textStyle: textStyle,
          ),
          child: child,
        ),
      AppButtonVariant.ghost => TextButton(
          onPressed: effectiveOnPressed,
          style: TextButton.styleFrom(
            minimumSize: minimumSize,
            padding: padding,
            shape: shape,
            textStyle: textStyle,
          ),
          child: child,
        ),
      AppButtonVariant.danger => OutlinedButton(
          onPressed: effectiveOnPressed,
          style: OutlinedButton.styleFrom(
            minimumSize: minimumSize,
            padding: padding,
            shape: shape,
            textStyle: textStyle,
            foregroundColor: AppColors.danger,
            side: BorderSide(
              color: AppColors.danger.withValues(alpha: 0.4),
            ),
          ),
          child: child,
        ),
    };

    return isExpanded
        ? SizedBox(width: double.infinity, child: button)
        : button;
  }
}
