import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../core/widgets/async_value_view.dart';
import '../../../../core/widgets/empty_state.dart';
import '../../../../core/widgets/primary_button.dart';
import '../../../offers/domain/entities/offer.dart';
import '../../../offers/presentation/providers/offer_providers.dart';
import '../../../salons/domain/entities/salon.dart';
import '../../../salons/presentation/providers/salon_providers.dart';
import '../providers/owner_providers.dart';

/// Owner offer management: create time-boxed discounts, toggle, delete.
class ManageOffersScreen extends ConsumerWidget {
  const ManageOffersScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final salon = ref.watch(ownerSalonProvider).valueOrNull;
    if (salon == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    final offers = ref.watch(salonOffersProvider(salon.id));

    return Scaffold(
      appBar: AppBar(title: const Text('Offers')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _OfferFormSheet.show(context, salon: salon),
        icon: const Icon(Icons.add_rounded),
        label: const Text('New offer'),
      ),
      body: AsyncValueView(
        value: offers,
        onRetry: () => ref.invalidate(salonOffersProvider(salon.id)),
        data: (items) => items.isEmpty
            ? const EmptyState(
                icon: Icons.local_offer_outlined,
                title: 'No offers yet',
                message: 'Time-boxed deals put you in "Hot deals near you" '
                    'on every customer\'s home screen.',
              )
            : ListView.separated(
                padding: const EdgeInsets.fromLTRB(20, 20, 20, 96),
                itemCount: items.length,
                separatorBuilder: (_, __) => const SizedBox(height: 10),
                itemBuilder: (context, index) =>
                    _OfferTile(offer: items[index]),
              ),
      ),
    );
  }
}

class _OfferTile extends ConsumerWidget {
  const _OfferTile({required this.offer});

  final Offer offer;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final actions = ref.read(ownerActionsProvider);
    final live = offer.isLiveAt(DateTime.now());

    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        child: Row(
          children: [
            Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: (live ? AppColors.success : AppColors.textSecondary)
                    .withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                '-${offer.discountPercent}%',
                style: TextStyle(
                  fontWeight: FontWeight.w800,
                  color: live ? AppColors.success : AppColors.textSecondary,
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(offer.title,
                      style: const TextStyle(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 2),
                  Text(
                    '${Formatters.dayTime(offer.startTime)} → '
                    '${Formatters.dayTime(offer.endTime)}'
                    '${offer.maxRedemptions > 0 ? ' · ${offer.redemptionCount}/${offer.maxRedemptions} used' : ''}',
                    style: const TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),
            Switch(
              value: offer.active,
              onChanged: (value) => actions.setOfferActive(offer.id, value),
            ),
            IconButton(
              icon: const Icon(Icons.delete_outline_rounded,
                  color: AppColors.danger),
              onPressed: () => actions.deleteOffer(offer.id),
            ),
          ],
        ),
      ),
    );
  }
}

/// Bottom-sheet form for creating an offer.
class _OfferFormSheet extends ConsumerStatefulWidget {
  const _OfferFormSheet({required this.salon});

  final Salon salon;

  static Future<void> show(BuildContext context, {required Salon salon}) =>
      showModalBottomSheet(
        context: context,
        isScrollControlled: true,
        showDragHandle: true,
        builder: (context) => _OfferFormSheet(salon: salon),
      );

  @override
  ConsumerState<_OfferFormSheet> createState() => _OfferFormSheetState();
}

class _OfferFormSheetState extends ConsumerState<_OfferFormSheet> {
  final _formKey = GlobalKey<FormState>();
  final _titleController = TextEditingController();
  final _maxRedemptionsController = TextEditingController(text: '0');
  int _discountPercent = 20;
  late DateTime _start;
  late DateTime _end;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    // Sensible default: a happy-hour style window later today (3pm–6pm).
    final now = DateTime.now();
    _start = DateTime(now.year, now.month, now.day, 15);
    if (_start.isBefore(now)) _start = now;
    _end = DateTime(now.year, now.month, now.day, 18);
    if (!_end.isAfter(_start)) _end = _start.add(const Duration(hours: 3));
  }

  @override
  void dispose() {
    _titleController.dispose();
    _maxRedemptionsController.dispose();
    super.dispose();
  }

  Future<void> _pick(bool isStart) async {
    final base = isStart ? _start : _end;
    final date = await showDatePicker(
      context: context,
      initialDate: base,
      firstDate: DateTime.now().subtract(const Duration(days: 1)),
      lastDate: DateTime.now().add(const Duration(days: 60)),
    );
    if (date == null || !mounted) return;
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(base),
    );
    if (time == null) return;
    final picked =
        DateTime(date.year, date.month, date.day, time.hour, time.minute);
    setState(() {
      if (isStart) {
        _start = picked;
        if (!_end.isAfter(_start)) {
          _end = _start.add(const Duration(hours: 3));
        }
      } else {
        _end = picked;
      }
    });
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (!_end.isAfter(_start)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('End time must be after start time')),
      );
      return;
    }
    setState(() => _submitting = true);
    try {
      final offer = Offer(
        id: '',
        salonId: widget.salon.id,
        salonName: widget.salon.name,
        title: _titleController.text.trim(),
        discountPercent: _discountPercent,
        startTime: _start,
        endTime: _end,
        active: true,
        maxRedemptions:
            int.tryParse(_maxRedemptionsController.text.trim()) ?? 0,
        redemptionCount: 0,
        createdAt: DateTime.now(),
      );
      await ref.read(ownerActionsProvider).createOffer(offer);
      if (mounted) Navigator.of(context).pop();
    } on Exception catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.toString())));
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    const discounts = [10, 15, 20, 25, 30, 40, 50];
    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: Form(
        key: _formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('New offer', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 20),
              TextFormField(
                controller: _titleController,
                textCapitalization: TextCapitalization.sentences,
                decoration: const InputDecoration(
                  labelText: 'Title',
                  hintText: 'e.g. Afternoon happy hour',
                ),
                validator: (v) =>
                    (v == null || v.trim().isEmpty) ? 'Required' : null,
              ),
              const SizedBox(height: 20),
              const Text('Discount',
                  style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: [
                  for (final percent in discounts)
                    ChoiceChip(
                      label: Text('$percent%'),
                      selected: _discountPercent == percent,
                      onSelected: (_) =>
                          setState(() => _discountPercent = percent),
                    ),
                ],
              ),
              const SizedBox(height: 20),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.play_circle_outline_rounded),
                title: const Text('Starts'),
                subtitle: Text(Formatters.dayTime(_start)),
                onTap: () => _pick(true),
              ),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.stop_circle_outlined),
                title: const Text('Ends'),
                subtitle: Text(Formatters.dayTime(_end)),
                onTap: () => _pick(false),
              ),
              const SizedBox(height: 8),
              TextFormField(
                controller: _maxRedemptionsController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Max redemptions (0 = unlimited)',
                  prefixIcon: Icon(Icons.confirmation_number_outlined),
                ),
              ),
              const SizedBox(height: 24),
              PrimaryButton(
                label: 'Publish offer',
                loading: _submitting,
                onPressed: _submit,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
