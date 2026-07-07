import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/widgets/primary_button.dart';
import '../../../salons/domain/entities/salon.dart';
import '../../../salons/domain/entities/salon_filters.dart';
import '../../../salons/presentation/providers/salon_providers.dart';

/// Bottom-sheet filters: audience (gender), price range, minimum rating.
class FilterSheet extends ConsumerStatefulWidget {
  const FilterSheet({super.key});

  static Future<void> show(BuildContext context) => showModalBottomSheet(
        context: context,
        isScrollControlled: true,
        showDragHandle: true,
        builder: (context) => const FilterSheet(),
      );

  @override
  ConsumerState<FilterSheet> createState() => _FilterSheetState();
}

class _FilterSheetState extends ConsumerState<FilterSheet> {
  late SalonAudience? _audience;
  late RangeValues _priceRange;
  late double _minRating;

  @override
  void initState() {
    super.initState();
    final current = ref.read(salonFiltersProvider);
    _audience = current.audience;
    _priceRange = RangeValues(current.minPrice, current.maxPrice);
    _minRating = current.minRating;
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Filters', style: Theme.of(context).textTheme.titleLarge),
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
              for (final audience in SalonAudience.values)
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
                    ref.read(salonFiltersProvider.notifier).reset();
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
                    ref.read(salonFiltersProvider.notifier).apply(
                          SalonFilters(
                            audience: _audience,
                            minRating: _minRating,
                            minPrice: _priceRange.start,
                            maxPrice: _priceRange.end,
                          ),
                        );
                    Navigator.of(context).pop();
                  },
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
