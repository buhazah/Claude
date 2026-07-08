import 'package:flutter/widgets.dart';

/// Spacing tokens — a strict 4pt grid.
///
/// Rules:
///  * Screens use tokens, never magic numbers. `13` is a bug; `12` or `16`
///    is a decision.
///  * Horizontal screen gutter is always [screenPadding] (20) so every
///    screen's content rail lines up.
///  * Sibling groups are laid out with gap-based layout (Column/Row +
///    SizedBox gap tokens, or Wrap spacing) — not per-child margins.
abstract final class AppSpacing {
  static const double xxs = 2;
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 20;
  static const double xxl = 24;
  static const double xxxl = 32;
  static const double huge = 40;

  /// Standard horizontal screen gutter.
  static const EdgeInsets screenPadding = EdgeInsets.symmetric(horizontal: xl);

  /// Standard inner padding of cards and tiles.
  static const EdgeInsets cardPadding = EdgeInsets.all(lg);

  /// Standard bottom-sheet content padding (keyboard inset added by the
  /// sheet component itself).
  static const EdgeInsets sheetPadding =
      EdgeInsets.symmetric(horizontal: xl, vertical: xl);

  // Gap widgets for gap-based layout.
  static const SizedBox gapXs = SizedBox(height: xs, width: xs);
  static const SizedBox gapSm = SizedBox(height: sm, width: sm);
  static const SizedBox gapMd = SizedBox(height: md, width: md);
  static const SizedBox gapLg = SizedBox(height: lg, width: lg);
  static const SizedBox gapXl = SizedBox(height: xl, width: xl);
  static const SizedBox gapXxl = SizedBox(height: xxl, width: xxl);
}
