import 'package:flutter/material.dart';

import '../../../../core/design_system/design_system.dart';
import '../../../../core/utils/formatters.dart';
import '../../../offers/domain/entities/offer.dart';

/// Feature adapter: maps an [Offer] onto the design-system [AppOfferCard].
class OfferCard extends StatelessWidget {
  const OfferCard({super.key, required this.offer, required this.onTap});

  final Offer offer;
  final VoidCallback onTap;

  String get _untilLabel => offer.hasDailyWindow
      ? 'daily until ${Formatters.minutesOfDay(offer.dailyEndMinute!)}'
      : 'until ${Formatters.time(offer.endTime)}';

  @override
  Widget build(BuildContext context) {
    return AppOfferCard(
      discountLabel: '-${offer.discountPercent}%',
      title: offer.title,
      subtitle: offer.businessName,
      untilLabel: _untilLabel,
      onTap: onTap,
    );
  }
}
