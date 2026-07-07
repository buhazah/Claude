import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../core/utils/geo_utils.dart';
import '../../../../core/widgets/rating_badge.dart';
import '../../../salons/domain/entities/salon.dart';

/// Discovery list card: cover image, name, audience, rating, distance, price.
class SalonCard extends StatelessWidget {
  const SalonCard({
    super.key,
    required this.salon,
    required this.distanceKm,
    required this.onTap,
  });

  final Salon salon;
  final double distanceKm;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            AspectRatio(
              aspectRatio: 16 / 8,
              child: salon.coverImage == null
                  ? Container(
                      color: AppColors.primary.withValues(alpha: 0.08),
                      child: const Icon(
                        Icons.spa_rounded,
                        size: 48,
                        color: AppColors.primary,
                      ),
                    )
                  : CachedNetworkImage(
                      imageUrl: salon.coverImage!,
                      fit: BoxFit.cover,
                      errorWidget: (_, __, ___) => const ColoredBox(
                        color: AppColors.background,
                        child: Icon(Icons.broken_image_outlined),
                      ),
                    ),
            ),
            Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          salon.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: 16,
                          ),
                        ),
                      ),
                      RatingBadge(
                        rating: salon.rating,
                        count: salon.ratingCount,
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      _Tag(label: salon.audience.label),
                      const SizedBox(width: 8),
                      const Icon(Icons.place_outlined,
                          size: 14, color: AppColors.textSecondary),
                      const SizedBox(width: 2),
                      Text(
                        GeoUtils.formatDistance(distanceKm),
                        style: const TextStyle(
                          color: AppColors.textSecondary,
                          fontSize: 13,
                        ),
                      ),
                      const Spacer(),
                      if (salon.startingPrice > 0)
                        Text(
                          'from ${Formatters.price(salon.startingPrice)}',
                          style: const TextStyle(
                            color: AppColors.primary,
                            fontWeight: FontWeight.w600,
                            fontSize: 13,
                          ),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Tag extends StatelessWidget {
  const _Tag({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: AppColors.primaryDark,
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
