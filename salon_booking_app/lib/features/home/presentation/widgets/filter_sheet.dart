import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/design_system/design_system.dart';
import '../../../businesses/domain/entities/business.dart';
import '../../../businesses/domain/entities/discovery_filters.dart';
import '../../../businesses/presentation/providers/business_providers.dart';

/// Bottom-sheet filters: category, audience (gender), price range, rating.
class FilterSheet extends ConsumerStatefulWidget {
  const FilterSheet({super.key});

  static Future<void> show(BuildContext context) => showAppBottomSheet(
        context: context,
        title: 'Filters',
        builder: (context) => const FilterSheet(),
      );

  @override
  ConsumerState<FilterSheet> createState() => _FilterSheetState();
}

class _FilterSheetState extends ConsumerState<FilterSheet> {
  late Audience? _audience;
  late BusinessCategory? _category;
  late RangeValues _priceRange;
  late double _minRating;

  @override
  void initState() {
    super.initState();
    final current = ref.read(discoveryFiltersProvider);
    _audience = current.audience;
    _category = current.category;
    _priceRange = RangeValues(current.minPriceAed, current.maxPriceAed);
    _minRating = current.minRating;
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Category', style: AppTypography.subtitle),
        AppSpacing.gapSm,
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: [
            AppFilterChip(
              label: 'All',
              selected: _category == null,
              onSelected: (_) => setState(() => _category = null),
            ),
            for (final category in BusinessCategory.values)
              AppFilterChip(
                label: category.label,
                selected: _category == category,
                onSelected: (_) => setState(() => _category = category),
              ),
          ],
        ),
        AppSpacing.gapXl,
        Text('For', style: AppTypography.subtitle),
        AppSpacing.gapSm,
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: [
            AppFilterChip(
              label: 'Any',
              selected: _audience == null,
              onSelected: (_) => setState(() => _audience = null),
            ),
            for (final audience in Audience.values)
              AppFilterChip(
                label: audience.label,
                selected: _audience == audience,
                onSelected: (_) => setState(() => _audience = audience),
              ),
          ],
        ),
        AppSpacing.gapXl,
        Text(
          'Price range (${AppConstants.currencySymbol} '
          '${_priceRange.start.round()} – ${_priceRange.end.round()})',
          style: AppTypography.subtitle,
        ),
        RangeSlider(
          values: _priceRange,
          min: AppConstants.minFilterPrice,
          max: AppConstants.maxFilterPrice,
          divisions: 20,
          onChanged: (values) => setState(() => _priceRange = values),
        ),
        AppSpacing.gapSm,
        Text(
          'Minimum rating (${_minRating.toStringAsFixed(1)}+)',
          style: AppTypography.subtitle,
        ),
        Slider(
          value: _minRating,
          min: 0,
          max: 5,
          divisions: 10,
          onChanged: (value) => setState(() => _minRating = value),
        ),
        AppSpacing.gapLg,
        Row(
          children: [
            Expanded(
              child: AppButton(
                label: 'Reset',
                variant: AppButtonVariant.secondary,
                onPressed: () {
                  ref.read(discoveryFiltersProvider.notifier).reset();
                  Navigator.of(context).pop();
                },
              ),
            ),
            AppSpacing.gapMd,
            Expanded(
              flex: 2,
              child: AppButton(
                label: 'Apply',
                onPressed: () {
                  ref.read(discoveryFiltersProvider.notifier).apply(
                        DiscoveryFilters(
                          audience: _audience,
                          category: _category,
                          minRating: _minRating,
                          minPriceAed: _priceRange.start,
                          maxPriceAed: _priceRange.end,
                        ),
                      );
                  Navigator.of(context).pop();
                },
              ),
            ),
          ],
        ),
      ],
    );
  }
}
