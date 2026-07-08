import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/widgets/app_sheet.dart';
import '../../../../core/widgets/primary_button.dart';
import '../../../businesses/domain/entities/business.dart';
import '../../../businesses/domain/entities/discovery_filters.dart';
import '../../../businesses/presentation/providers/business_providers.dart';

/// Bottom-sheet filters: category, audience (gender), price range, rating.
class FilterSheet extends ConsumerStatefulWidget {
  const FilterSheet({super.key});

  static Future<void> show(BuildContext context) => showAppSheet(
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
        const Text('Category', style: TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            ChoiceChip(
              label: const Text('All'),
              selected: _category == null,
              onSelected: (_) => setState(() => _category = null),
            ),
            for (final category in BusinessCategory.values)
              ChoiceChip(
                label: Text(category.label),
                selected: _category == category,
                onSelected: (_) => setState(() => _category = category),
              ),
          ],
        ),
        const SizedBox(height: 20),
        const Text('For', style: TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          children: [
            ChoiceChip(
              label: const Text('Any'),
              selected: _audience == null,
              onSelected: (_) => setState(() => _audience = null),
            ),
            for (final audience in Audience.values)
              ChoiceChip(
                label: Text(audience.label),
                selected: _audience == audience,
                onSelected: (_) => setState(() => _audience = audience),
              ),
          ],
        ),
        const SizedBox(height: 20),
        Text(
          'Price range (${AppConstants.currencySymbol} '
          '${_priceRange.start.round()} – ${_priceRange.end.round()})',
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        RangeSlider(
          values: _priceRange,
          min: AppConstants.minFilterPrice,
          max: AppConstants.maxFilterPrice,
          divisions: 20,
          onChanged: (values) => setState(() => _priceRange = values),
        ),
        const SizedBox(height: 8),
        Text(
          'Minimum rating (${_minRating.toStringAsFixed(1)}+)',
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        Slider(
          value: _minRating,
          min: 0,
          max: 5,
          divisions: 10,
          onChanged: (value) => setState(() => _minRating = value),
        ),
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: () {
                  ref.read(discoveryFiltersProvider.notifier).reset();
                  Navigator.of(context).pop();
                },
                child: const Text('Reset'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              flex: 2,
              child: PrimaryButton(
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
