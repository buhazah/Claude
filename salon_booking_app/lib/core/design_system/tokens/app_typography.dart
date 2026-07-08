import 'package:flutter/material.dart';

import 'app_colors.dart';

/// Typography tokens.
///
/// Uses the platform face (SF Pro on iOS, Roboto on Android) tuned with
/// tight tracking on large sizes and generous line-height on body — the
/// Apple/Stripe recipe: hierarchy through weight and spacing, not
/// decoration. A brand font (e.g. Plus Jakarta Sans) can be dropped in
/// later by setting `fontFamily` in [AppTheme] only.
///
/// Rules:
///  * Prices and any column of digits use [price] / [tabularFigures] so
///    numbers align.
///  * [label] is for uppercase micro-labels and must ship with its
///    letter-spacing — never fake it with a shrunken title style.
abstract final class AppTypography {
  static const List<FontFeature> tabularFigures = [
    FontFeature.tabularFigures(),
  ];

  // --- Display / headings -------------------------------------------------
  static const TextStyle display = TextStyle(
    fontSize: 32,
    height: 1.15,
    fontWeight: FontWeight.w800,
    letterSpacing: -0.6,
    color: AppColors.textPrimary,
  );

  static const TextStyle headline = TextStyle(
    fontSize: 24,
    height: 1.2,
    fontWeight: FontWeight.w800,
    letterSpacing: -0.4,
    color: AppColors.textPrimary,
  );

  static const TextStyle title = TextStyle(
    fontSize: 18,
    height: 1.25,
    fontWeight: FontWeight.w700,
    letterSpacing: -0.2,
    color: AppColors.textPrimary,
  );

  static const TextStyle subtitle = TextStyle(
    fontSize: 15,
    height: 1.35,
    fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
  );

  // --- Body ----------------------------------------------------------------
  static const TextStyle body = TextStyle(
    fontSize: 14,
    height: 1.45,
    fontWeight: FontWeight.w400,
    color: AppColors.textPrimary,
  );

  static const TextStyle bodyStrong = TextStyle(
    fontSize: 14,
    height: 1.45,
    fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
  );

  static const TextStyle bodyMuted = TextStyle(
    fontSize: 14,
    height: 1.45,
    fontWeight: FontWeight.w400,
    color: AppColors.textSecondary,
  );

  // --- Small ----------------------------------------------------------------
  static const TextStyle caption = TextStyle(
    fontSize: 12,
    height: 1.35,
    fontWeight: FontWeight.w400,
    color: AppColors.textSecondary,
  );

  /// Uppercase micro-label ("SERVICES", "TODAY").
  static const TextStyle label = TextStyle(
    fontSize: 11,
    height: 1.2,
    fontWeight: FontWeight.w700,
    letterSpacing: 1.1,
    color: AppColors.textSecondary,
  );

  // --- Numbers ---------------------------------------------------------------
  static const TextStyle price = TextStyle(
    fontSize: 16,
    height: 1.2,
    fontWeight: FontWeight.w800,
    color: AppColors.primary,
    fontFeatures: tabularFigures,
  );

  static const TextStyle priceSmall = TextStyle(
    fontSize: 13,
    height: 1.2,
    fontWeight: FontWeight.w700,
    color: AppColors.primary,
    fontFeatures: tabularFigures,
  );

  static const TextStyle priceStruck = TextStyle(
    fontSize: 12,
    height: 1.2,
    fontWeight: FontWeight.w500,
    color: AppColors.textSecondary,
    decoration: TextDecoration.lineThrough,
    fontFeatures: tabularFigures,
  );

  /// Material TextTheme derived from the tokens, for [ThemeData.textTheme].
  static TextTheme textTheme({
    required Color primaryText,
    required Color secondaryText,
  }) =>
      TextTheme(
        displaySmall: display.copyWith(color: primaryText),
        headlineSmall: headline.copyWith(color: primaryText),
        titleLarge: title.copyWith(color: primaryText),
        titleMedium: subtitle.copyWith(color: primaryText),
        bodyLarge: body.copyWith(fontSize: 15, color: primaryText),
        bodyMedium: body.copyWith(color: primaryText),
        bodySmall: caption.copyWith(color: secondaryText),
        labelLarge: bodyStrong.copyWith(color: primaryText),
        labelSmall: label.copyWith(color: secondaryText),
      );
}
