import 'package:flutter/material.dart';

import '../tokens/app_colors.dart';
import '../tokens/app_motion.dart';
import '../tokens/app_radius.dart';
import '../tokens/app_spacing.dart';
import '../tokens/app_typography.dart';

/// Central Material 3 themes, derived entirely from the design tokens.
///
/// [dark] is production-ready but the app pins ThemeMode.light until the
/// screen-migration phase removes direct static-color references from
/// screens (see docs/DESIGN_SYSTEM.md → "Dark mode").
abstract final class AppTheme {
  static ThemeData light() => _build(
        brightness: Brightness.light,
        scheme: ColorScheme.fromSeed(
          seedColor: AppColors.primary,
          primary: AppColors.primary,
          secondary: AppColors.accent,
          surface: AppColors.surface,
          error: AppColors.danger,
        ),
        background: AppColors.background,
        surface: AppColors.surface,
        border: AppColors.border,
        textPrimary: AppColors.textPrimary,
        textSecondary: AppColors.textSecondary,
        primary: AppColors.primary,
        primarySubtle: AppColors.primarySubtle,
      );

  static ThemeData dark() => _build(
        brightness: Brightness.dark,
        scheme: ColorScheme.fromSeed(
          brightness: Brightness.dark,
          seedColor: AppColorsDark.primary,
          primary: AppColorsDark.primary,
          secondary: AppColorsDark.accent,
          surface: AppColorsDark.surface,
          error: AppColors.danger,
        ),
        background: AppColorsDark.background,
        surface: AppColorsDark.surface,
        border: AppColorsDark.border,
        textPrimary: AppColorsDark.textPrimary,
        textSecondary: AppColorsDark.textSecondary,
        primary: AppColorsDark.primary,
        primarySubtle: AppColorsDark.primarySubtle,
      );

  static ThemeData _build({
    required Brightness brightness,
    required ColorScheme scheme,
    required Color background,
    required Color surface,
    required Color border,
    required Color textPrimary,
    required Color textSecondary,
    required Color primary,
    required Color primarySubtle,
  }) {
    final textTheme = AppTypography.textTheme(
      primaryText: textPrimary,
      secondaryText: textSecondary,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      scaffoldBackgroundColor: background,
      textTheme: textTheme,
      splashFactory: InkSparkle.splashFactory,

      appBarTheme: AppBarTheme(
        backgroundColor: background,
        foregroundColor: textPrimary,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: AppTypography.title.copyWith(
          fontSize: 20,
          color: textPrimary,
        ),
      ),

      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        shape: const RoundedRectangleBorder(borderRadius: AppRadius.cardAll),
        margin: EdgeInsets.zero,
      ),

      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(52),
          shape: const RoundedRectangleBorder(
            borderRadius: AppRadius.controlAll,
          ),
          textStyle: AppTypography.bodyStrong.copyWith(fontSize: 16),
          animationDuration: AppMotion.fast,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size.fromHeight(52),
          side: BorderSide(color: border),
          shape: const RoundedRectangleBorder(
            borderRadius: AppRadius.controlAll,
          ),
          textStyle: AppTypography.bodyStrong.copyWith(fontSize: 15),
          animationDuration: AppMotion.fast,
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          textStyle: AppTypography.bodyStrong,
          animationDuration: AppMotion.fast,
        ),
      ),

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surface,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.lg,
          vertical: AppSpacing.md + 2,
        ),
        border: const OutlineInputBorder(
          borderRadius: AppRadius.fieldAll,
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: AppRadius.fieldAll,
          borderSide: BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: AppRadius.fieldAll,
          borderSide: BorderSide(color: primary, width: 1.5),
        ),
        hintStyle: AppTypography.body.copyWith(color: textSecondary),
      ),

      chipTheme: ChipThemeData(
        shape: const RoundedRectangleBorder(borderRadius: AppRadius.chipAll),
        side: BorderSide.none,
        backgroundColor: surface,
        selectedColor: primarySubtle,
        labelStyle: AppTypography.bodyStrong.copyWith(
          fontSize: 13,
          color: textPrimary,
        ),
      ),

      bottomNavigationBarTheme: BottomNavigationBarThemeData(
        backgroundColor: surface,
        selectedItemColor: primary,
        unselectedItemColor: textSecondary,
        type: BottomNavigationBarType.fixed,
        selectedLabelStyle:
            AppTypography.caption.copyWith(fontWeight: FontWeight.w700),
        unselectedLabelStyle: AppTypography.caption,
      ),

      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: surface,
        surfaceTintColor: Colors.transparent,
        shape: const RoundedRectangleBorder(borderRadius: AppRadius.sheetTop),
        showDragHandle: true,
        modalBarrierColor: AppColors.overlay,
      ),

      dialogTheme: DialogThemeData(
        backgroundColor: surface,
        surfaceTintColor: Colors.transparent,
        shape: const RoundedRectangleBorder(borderRadius: AppRadius.cardAll),
        titleTextStyle: AppTypography.title.copyWith(color: textPrimary),
        contentTextStyle: AppTypography.body.copyWith(color: textSecondary),
      ),

      tabBarTheme: TabBarThemeData(
        labelColor: primary,
        unselectedLabelColor: textSecondary,
        labelStyle: AppTypography.bodyStrong,
        unselectedLabelStyle: AppTypography.bodyStrong,
        indicatorColor: primary,
        dividerColor: border,
      ),

      dividerTheme: DividerThemeData(color: border, thickness: 1, space: 1),

      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: primary,
        foregroundColor: AppColors.textOnPrimary,
        elevation: 3,
        shape: const RoundedRectangleBorder(borderRadius: AppRadius.fieldAll),
        extendedTextStyle: AppTypography.bodyStrong.copyWith(fontSize: 15),
      ),

      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: textPrimary,
        contentTextStyle: AppTypography.bodyStrong.copyWith(
          color: surface,
        ),
        shape: const RoundedRectangleBorder(borderRadius: AppRadius.controlAll),
      ),
    );
  }
}
