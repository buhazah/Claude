import 'package:flutter/widgets.dart';

/// Shadow tokens — soft, violet-tinted, low-alpha layers.
///
/// Premium depth comes from *two* faint layers (ambient + key), never one
/// heavy drop shadow. Shadows are tinted with the brand ink (0xFF17151F
/// family) so they sit naturally on the violet-tinted background.
///
/// Rules:
///  * Resting cards use [card]. Only elements that float above content
///    (FABs, popovers, the confirm bar) use [floating].
///  * Never put a shadow on something that also has a visible border — pick
///    one separation strategy per component.
abstract final class AppShadows {
  static const List<BoxShadow> none = [];

  /// Subtle lift for tiles inside an already-elevated context.
  static const List<BoxShadow> soft = [
    BoxShadow(
      color: Color(0x0F17151F), // 6%
      blurRadius: 12,
      offset: Offset(0, 4),
    ),
  ];

  /// Resting cards (business cards, booking cards).
  static const List<BoxShadow> card = [
    BoxShadow(
      color: Color(0x0D17151F), // 5% ambient
      blurRadius: 20,
      offset: Offset(0, 8),
    ),
    BoxShadow(
      color: Color(0x0A17151F), // 4% key
      blurRadius: 4,
      offset: Offset(0, 2),
    ),
  ];

  /// Floating elements: FABs, sticky confirm bars, popovers.
  static const List<BoxShadow> floating = [
    BoxShadow(
      color: Color(0x242A1655), // 14% violet-tinted
      blurRadius: 24,
      offset: Offset(0, 10),
    ),
  ];

  /// Modal sheets sliding over content.
  static const List<BoxShadow> modal = [
    BoxShadow(
      color: Color(0x3317151F), // 20%
      blurRadius: 40,
      offset: Offset(0, -8),
    ),
  ];
}
