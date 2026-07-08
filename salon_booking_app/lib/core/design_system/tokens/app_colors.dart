import 'package:flutter/material.dart';

/// Color tokens — light theme (canonical).
///
/// Premium marketplace palette: a deep violet brand anchor (trust,
/// indulgence), warm gold accent (UAE premium cue), violet-tinted neutrals
/// so greys never read as "unstyled", and a semantic set kept separate from
/// the brand hue.
///
/// Rules:
///  * Screens reference tokens (or Theme/ColorScheme) — never inline hex.
///  * Semantic colors (success/warning/danger/info) are for state, never
///    decoration.
///  * The accent gold is a garnish (badges, highlights) — the primary CTA
///    color is always the violet.
abstract final class AppColors {
  // --- Brand -------------------------------------------------------------
  static const Color primary = Color(0xFF6C4AB6); // deep violet
  static const Color primaryDark = Color(0xFF4B2E92);
  static const Color primaryLight = Color(0xFF9E85DC);

  /// 8–12% violet washes for selected states / icon plates.
  static const Color primarySubtle = Color(0xFFF0EBFA);

  static const Color accent = Color(0xFFE8B86D); // warm gold
  static const Color accentDeep = Color(0xFFB98A45);
  static const Color accentSubtle = Color(0xFFFBF1E1);

  // --- Surfaces ----------------------------------------------------------
  static const Color background = Color(0xFFF8F7FB);
  static const Color surface = Colors.white;

  /// Nested surfaces (input fills, list-item plates on cards).
  static const Color surfaceAlt = Color(0xFFF1EFF7);
  static const Color border = Color(0xFFE8E5F0);

  /// Scrim behind sheets/dialogs.
  static const Color overlay = Color(0x8C17151F);

  // --- Text --------------------------------------------------------------
  static const Color textPrimary = Color(0xFF1D1B26);
  static const Color textSecondary = Color(0xFF6E6A7C);
  static const Color textTertiary = Color(0xFF9A95A8);
  static const Color textOnPrimary = Colors.white;

  // --- Semantic ----------------------------------------------------------
  static const Color success = Color(0xFF2E9E6B);
  static const Color warning = Color(0xFFE8A13D);
  static const Color danger = Color(0xFFD64550);
  static const Color info = Color(0xFF4E7FE1);

  // --- Booking status ------------------------------------------------------
  static const Color statusPending = warning;
  static const Color statusConfirmed = success;
  static const Color statusCancelled = danger;
  static const Color statusCompleted = Color(0xFF5B8DEF);

  // --- Component-specific --------------------------------------------------
  /// Skeleton/shimmer base.
  static const Color skeleton = Color(0xFFECE9F3);

  /// Star/rating fill.
  static const Color rating = accent;
}

/// Color tokens — dark theme.
///
/// Ready for the screen-migration phase: [AppTheme.dark] is built from
/// these, but the app pins ThemeMode.light until screens stop referencing
/// static light tokens directly.
abstract final class AppColorsDark {
  static const Color primary = Color(0xFF9E85DC);
  static const Color primaryDark = Color(0xFF7B5EC6);
  static const Color primarySubtle = Color(0xFF2B2438);

  static const Color accent = Color(0xFFE5BE7F);

  static const Color background = Color(0xFF141218);
  static const Color surface = Color(0xFF1D1A24);
  static const Color surfaceAlt = Color(0xFF262230);
  static const Color border = Color(0xFF322D40);

  static const Color textPrimary = Color(0xFFF4F2F8);
  static const Color textSecondary = Color(0xFFA9A3B8);
  static const Color textTertiary = Color(0xFF7A7490);

  static const Color skeleton = Color(0xFF2A2536);
}
