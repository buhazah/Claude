import 'package:flutter/material.dart';

/// Brand palette. Screens must reference theme/scheme colors (or these
/// tokens) — never inline hex values.
abstract final class AppColors {
  // Brand
  static const Color primary = Color(0xFF6C4AB6); // deep violet
  static const Color primaryDark = Color(0xFF4B2E92);
  static const Color accent = Color(0xFFE8B86D); // warm gold

  // Surfaces
  static const Color background = Color(0xFFF8F7FB);
  static const Color surface = Colors.white;

  // Text
  static const Color textPrimary = Color(0xFF1D1B26);
  static const Color textSecondary = Color(0xFF6E6A7C);

  // Semantic
  static const Color success = Color(0xFF2E9E6B);
  static const Color warning = Color(0xFFE8A13D);
  static const Color danger = Color(0xFFD64550);

  // Booking status chips
  static const Color statusPending = warning;
  static const Color statusConfirmed = success;
  static const Color statusCancelled = danger;
  static const Color statusCompleted = Color(0xFF5B8DEF);
}
