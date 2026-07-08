import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/errors/error_text.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../core/widgets/app_sheet.dart';
import '../../../../core/widgets/async_value_view.dart';
import '../../../../core/widgets/empty_state.dart';
import '../../../../core/widgets/primary_button.dart';
import '../../../businesses/domain/entities/business.dart';
import '../../../businesses/presentation/providers/business_providers.dart';
import '../../../offers/domain/entities/offer.dart';
import '../../../offers/presentation/providers/offer_providers.dart';
import '../providers/owner_providers.dart';

/// Owner offer management: create time-boxed discounts (optionally with a
/// recurring daily window), toggle, delete.
class ManageOffersScreen extends ConsumerWidget {
  const ManageOffersScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final business = ref.watch(ownerBusinessProvider).valueOrNull;
    if (business == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    final offers = ref.watch(businessOffersProvider(business.id));

    return Scaffold(
      appBar: AppBar(title: const Text('Offers')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _OfferFormSheet.show(context, business: business),
        icon: const Icon(Icons.add_rounded),
        label: const Text('New offer'),
      ),
      body: AsyncValueView(
        value: offers,
        onRetry: () => ref.invalidate(businessOffersProvider(business.id)),
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
    final window = offer.hasDailyWindow
        ? 'daily ${Formatters.minutesOfDay(offer.dailyStartMinute!)}–'
            '${Formatters.minutesOfDay(offer.dailyEndMinute!)} · '
        : '';

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
                    '$window${Formatters.day(offer.startTime)} → '
                    '${Formatters.day(offer.endTime)}'
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
  const _OfferFormSheet({required this.business});

  final Business business;

  static Future<void> show(BuildContext context,
          {required Business business}) =>
      showAppSheet(
        context: context,
        title: 'New offer',
        builder: (context) => _OfferFormSheet(business: business),
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
  bool _useDailyWindow = false;
  TimeOfDay _dailyStart = const TimeOfDay(hour: 15, minute: 0);
  TimeOfDay _dailyEnd = const TimeOfDay(hour: 18, minute: 0);
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _start = DateTime(now.year, now.month, now.day);
    _end = _start.add(const Duration(days: 7));
  }

  @override
  void dispose() {
    _titleController.dispose();
    _maxRedemptionsController.dispose();
    super.dispose();
  }

  Future<void> _pickDate(bool isStart) async {
    final base = isStart ? _start : _end;
    final date = await showDatePicker(
      context: context,
      initialDate: base,
      firstDate: DateTime.now().subtract(const Duration(days: 1)),
      lastDate: DateTime.now().add(const Duration(days: 90)),
    );
    if (date == null) return;
    setState(() {
      if (isStart) {
        _start = DateTime(date.year, date.month, date.day);
        if (!_end.isAfter(_start)) {
          _end = _start.add(const Duration(days: 1));
        }
      } else {
        // End of the chosen day.
        _end = DateTime(date.year, date.month, date.day, 23, 59);
      }
    });
  }

  Future<void> _pickDailyTime(bool isStart) async {
    final picked = await showTimePicker(
      context: context,
      initialTime: isStart ? _dailyStart : _dailyEnd,
    );
    if (picked == null) return;
    setState(() {
      if (isStart) {
        _dailyStart = picked;
      } else {
        _dailyEnd = picked;
      }
    });
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (!_end.isAfter(_start)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('End date must be after start date')),
      );
      return;
    }
    final dailyStartMinute = _dailyStart.hour * 60 + _dailyStart.minute;
    final dailyEndMinute = _dailyEnd.hour * 60 + _dailyEnd.minute;
    if (_useDailyWindow && dailyEndMinute <= dailyStartMinute) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Daily window end must be after its start')),
      );
      return;
    }
    setState(() => _submitting = true);
    try {
      final offer = Offer(
        id: '',
        businessId: widget.business.id,
        businessName: widget.business.name,
        title: _titleController.text.trim(),
        discountPercent: _discountPercent,
        startTime: _start,
        endTime: _end,
        active: true,
        maxRedemptions:
            int.tryParse(_maxRedemptionsController.text.trim()) ?? 0,
        redemptionCount: 0,
        createdAt: DateTime.now(),
        dailyStartMinute: _useDailyWindow ? dailyStartMinute : null,
        dailyEndMinute: _useDailyWindow ? dailyEndMinute : null,
      );
      await ref.read(ownerActionsProvider).createOffer(offer);
      if (mounted) Navigator.of(context).pop();
    } on Exception catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(errorText(e))));
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    const discounts = [10, 15, 20, 25, 30, 40, 50];
    return Form(
      key: _formKey,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
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
          const SizedBox(height: 12),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.play_circle_outline_rounded),
            title: const Text('Runs from'),
            subtitle: Text(Formatters.day(_start)),
            onTap: () => _pickDate(true),
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.stop_circle_outlined),
            title: const Text('Until'),
            subtitle: Text(Formatters.day(_end)),
            onTap: () => _pickDate(false),
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Daily happy-hour window'),
            subtitle: const Text('e.g. only 3:00–6:00 PM each day'),
            value: _useDailyWindow,
            onChanged: (value) => setState(() => _useDailyWindow = value),
          ),
          if (_useDailyWindow)
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => _pickDailyTime(true),
                    child: Text('From ${_dailyStart.format(context)}'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => _pickDailyTime(false),
                    child: Text('To ${_dailyEnd.format(context)}'),
                  ),
                ),
              ],
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
    );
  }
}
