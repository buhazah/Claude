import 'package:flutter/animation.dart';

/// Motion tokens + guidelines.
///
/// The system's motion voice is *calm and immediate* (Uber): things settle
/// quickly with a decisive ease-out; nothing bounces, nothing loops for
/// decoration.
///
/// Guidelines:
///  * State changes (chip select, toggle, color) → [fast] + [standard].
///  * Element entrances (cards, sheets, banners) → [base] + [emphasized],
///    fading in while translating ≤ 16px.
///  * Screen transitions → [page]; never longer.
///  * Lists may stagger children by [staggerStep], capped at ~6 items —
///    beyond that the stagger reads as lag.
///  * Skeletons pulse with [skeletonPulse]; that is the only permitted
///    looping animation.
///  * Always respect `MediaQuery.disableAnimations` — components with
///    looping or entrance motion must render their final frame statically
///    when it is set.
abstract final class AppMotion {
  // Durations
  static const Duration instant = Duration(milliseconds: 100);
  static const Duration fast = Duration(milliseconds: 150);
  static const Duration base = Duration(milliseconds: 250);
  static const Duration page = Duration(milliseconds: 300);
  static const Duration slow = Duration(milliseconds: 400);
  static const Duration skeletonPulse = Duration(milliseconds: 1100);

  /// Per-item delay when staggering list entrances.
  static const Duration staggerStep = Duration(milliseconds: 40);

  // Curves
  static const Curve standard = Curves.easeOutCubic;
  static const Curve emphasized = Curves.easeOutQuart;
  static const Curve exit = Curves.easeInCubic;
}
