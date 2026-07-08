import 'package:flutter/widgets.dart';

/// Border-radius tokens.
///
/// The scale reads as one system because each tier maps to a component
/// class — don't mix tiers within a component:
///  * badge (8)   — status pills, discount tags, tiny chips
///  * chip (10)   — filter chips, choice chips
///  * control (12)— buttons, small tappables
///  * field (14)  — text fields, search bars
///  * card (16)   — cards, tiles, banners
///  * sheet (24)  — bottom sheets, dialogs (top corners)
///  * pill (999)  — fully-rounded elements
abstract final class AppRadius {
  static const double badge = 8;
  static const double chip = 10;
  static const double control = 12;
  static const double field = 14;
  static const double card = 16;
  static const double sheet = 24;
  static const double pill = 999;

  static const BorderRadius badgeAll = BorderRadius.all(Radius.circular(badge));
  static const BorderRadius chipAll = BorderRadius.all(Radius.circular(chip));
  static const BorderRadius controlAll =
      BorderRadius.all(Radius.circular(control));
  static const BorderRadius fieldAll = BorderRadius.all(Radius.circular(field));
  static const BorderRadius cardAll = BorderRadius.all(Radius.circular(card));
  static const BorderRadius sheetTop = BorderRadius.vertical(
    top: Radius.circular(sheet),
  );
  static const BorderRadius pillAll = BorderRadius.all(Radius.circular(pill));
}
