import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../tokens/app_colors.dart';
import '../tokens/app_radius.dart';
import '../tokens/app_spacing.dart';
import '../tokens/app_typography.dart';
import 'app_rating_badge.dart';

/// Discovery card for a marketplace business (Airbnb-style: image leads,
/// facts follow). Entity-agnostic — takes display values, so feature code
/// adapts `Business` → card without the design system knowing the domain.
class AppBusinessCard extends StatelessWidget {
  const AppBusinessCard({
    super.key,
    required this.name,
    required this.onTap,
    this.imageUrl,
    this.rating,
    this.ratingCount,
    this.tag,
    this.distanceLabel,
    this.priceLabel,
    this.badge,
  });

  final String name;
  final VoidCallback onTap;
  final String? imageUrl;
  final double? rating;
  final int? ratingCount;

  /// Small category/audience tag ("Women", "Spa").
  final String? tag;

  /// "0.8 km"
  final String? distanceLabel;

  /// "from AED 90"
  final String? priceLabel;

  /// Overlay badge on the image ("-30%", "New").
  final String? badge;

  @override
  Widget build(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Stack(
              children: [
                AspectRatio(
                  aspectRatio: 16 / 8,
                  child: imageUrl == null
                      ? Container(
                          color: AppColors.primarySubtle,
                          child: const Icon(
                            Icons.storefront_rounded,
                            size: 48,
                            color: AppColors.primary,
                          ),
                        )
                      : CachedNetworkImage(
                          imageUrl: imageUrl!,
                          fit: BoxFit.cover,
                          errorWidget: (_, __, ___) => const ColoredBox(
                            color: AppColors.surfaceAlt,
                            child: Icon(
                              Icons.broken_image_outlined,
                              color: AppColors.textTertiary,
                            ),
                          ),
                        ),
                ),
                if (badge != null)
                  Positioned(
                    top: AppSpacing.md,
                    left: AppSpacing.md,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppSpacing.sm + 2,
                        vertical: AppSpacing.xs,
                      ),
                      decoration: const BoxDecoration(
                        color: AppColors.accent,
                        borderRadius: AppRadius.badgeAll,
                      ),
                      child: Text(
                        badge!,
                        style: AppTypography.bodyStrong.copyWith(
                          fontSize: 12,
                          color: AppColors.textPrimary,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
            Padding(
              padding: const EdgeInsets.all(AppSpacing.lg - 2),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: AppTypography.subtitle
                              .copyWith(fontWeight: FontWeight.w700),
                        ),
                      ),
                      if (rating != null)
                        AppRatingBadge(rating: rating!, count: ratingCount),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.sm - 2),
                  Row(
                    children: [
                      if (tag != null) ...[
                        _Tag(label: tag!),
                        const SizedBox(width: AppSpacing.sm),
                      ],
                      if (distanceLabel != null) ...[
                        const Icon(
                          Icons.place_outlined,
                          size: 14,
                          color: AppColors.textSecondary,
                        ),
                        const SizedBox(width: 2),
                        Text(
                          distanceLabel!,
                          style: AppTypography.caption.copyWith(fontSize: 13),
                        ),
                      ],
                      const Spacer(),
                      if (priceLabel != null)
                        Text(priceLabel!, style: AppTypography.priceSmall),
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
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: 3,
      ),
      decoration: const BoxDecoration(
        color: AppColors.primarySubtle,
        borderRadius: AppRadius.badgeAll,
      ),
      child: Text(
        label,
        style: AppTypography.bodyStrong.copyWith(
          fontSize: 12,
          color: AppColors.primaryDark,
        ),
      ),
    );
  }
}
