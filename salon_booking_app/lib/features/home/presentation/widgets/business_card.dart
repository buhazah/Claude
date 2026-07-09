import 'package:flutter/material.dart';

import '../../../../core/design_system/design_system.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../core/utils/geo_utils.dart';
import '../../../businesses/domain/entities/business.dart';

/// Feature adapter: maps a [Business] domain entity onto the design-system
/// [AppBusinessCard]. Keeps domain knowledge out of the design system.
class BusinessCard extends StatelessWidget {
  const BusinessCard({
    super.key,
    required this.business,
    required this.distanceKm,
    required this.onTap,
  });

  final Business business;
  final double distanceKm;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return AppBusinessCard(
      name: business.name,
      onTap: onTap,
      imageUrl: business.coverImage,
      rating: business.ratingCount > 0 ? business.rating : null,
      ratingCount: business.ratingCount > 0 ? business.ratingCount : null,
      tag: business.audience.label,
      distanceLabel: GeoUtils.formatDistance(distanceKm),
      priceLabel: business.startingPrice.isZero
          ? null
          : 'from ${Formatters.price(business.startingPrice)}',
    );
  }
}
