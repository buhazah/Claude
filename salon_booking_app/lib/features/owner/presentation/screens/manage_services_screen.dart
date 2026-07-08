import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/errors/error_text.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../core/utils/money.dart';
import '../../../../core/widgets/app_sheet.dart';
import '../../../../core/widgets/async_value_view.dart';
import '../../../../core/widgets/empty_state.dart';
import '../../../../core/widgets/primary_button.dart';
import '../../../businesses/domain/entities/service_offering.dart';
import '../../../businesses/presentation/providers/business_providers.dart';
import '../providers/owner_providers.dart';

/// Owner service management: add / edit / delete with price and duration.
class ManageServicesScreen extends ConsumerWidget {
  const ManageServicesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final business = ref.watch(ownerBusinessProvider).valueOrNull;
    if (business == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    final services = ref.watch(businessServicesProvider(business.id));

    return Scaffold(
      appBar: AppBar(title: const Text('Services')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () =>
            _ServiceFormSheet.show(context, businessId: business.id),
        icon: const Icon(Icons.add_rounded),
        label: const Text('Add service'),
      ),
      body: AsyncValueView(
        value: services,
        onRetry: () => ref.invalidate(businessServicesProvider(business.id)),
        data: (items) => items.isEmpty
            ? const EmptyState(
                icon: Icons.design_services_outlined,
                title: 'No services yet',
                message:
                    'Add your first service so customers can book you.',
              )
            : ListView.separated(
                padding: const EdgeInsets.fromLTRB(20, 20, 20, 96),
                itemCount: items.length,
                separatorBuilder: (_, __) => const SizedBox(height: 10),
                itemBuilder: (context, index) {
                  final service = items[index];
                  return Card(
                    child: ListTile(
                      title: Text(service.name,
                          style:
                              const TextStyle(fontWeight: FontWeight.w600)),
                      subtitle: Text(
                        '${Formatters.price(service.price)} · '
                        '${Formatters.duration(service.durationMinutes)}',
                      ),
                      trailing: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          IconButton(
                            icon: const Icon(Icons.edit_outlined),
                            onPressed: () => _ServiceFormSheet.show(
                              context,
                              businessId: business.id,
                              existing: service,
                            ),
                          ),
                          IconButton(
                            icon: const Icon(Icons.delete_outline_rounded,
                                color: AppColors.danger),
                            onPressed: () =>
                                _confirmDelete(context, ref, service),
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
      ),
    );
  }

  Future<void> _confirmDelete(
    BuildContext context,
    WidgetRef ref,
    ServiceOffering service,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Delete "${service.name}"?'),
        content: const Text('Existing bookings keep their snapshot of it.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await ref
          .read(ownerActionsProvider)
          .deleteService(service.id, service.businessId);
    }
  }
}

/// Bottom sheet form used for both "add" and "edit".
class _ServiceFormSheet extends ConsumerStatefulWidget {
  const _ServiceFormSheet({required this.businessId, this.existing});

  final String businessId;
  final ServiceOffering? existing;

  static Future<void> show(
    BuildContext context, {
    required String businessId,
    ServiceOffering? existing,
  }) =>
      showAppSheet(
        context: context,
        title: existing == null ? 'Add service' : 'Edit service',
        builder: (context) =>
            _ServiceFormSheet(businessId: businessId, existing: existing),
      );

  @override
  ConsumerState<_ServiceFormSheet> createState() => _ServiceFormSheetState();
}

class _ServiceFormSheetState extends ConsumerState<_ServiceFormSheet> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _nameController;
  late final TextEditingController _priceController;
  late int _durationMinutes;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _nameController =
        TextEditingController(text: widget.existing?.name ?? '');
    _priceController = TextEditingController(
      text: widget.existing == null
          ? ''
          : widget.existing!.price.aed.toStringAsFixed(0),
    );
    _durationMinutes = widget.existing?.durationMinutes ?? 30;
  }

  @override
  void dispose() {
    _nameController.dispose();
    _priceController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _submitting = true);
    try {
      final service = ServiceOffering(
        id: widget.existing?.id ?? '',
        businessId: widget.businessId,
        name: _nameController.text.trim(),
        price: Money.tryParseAed(_priceController.text)!,
        durationMinutes: _durationMinutes,
      );
      await ref.read(ownerActionsProvider).saveService(service);
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
    const durations = [15, 30, 45, 60, 90, 120];
    return Form(
      key: _formKey,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextFormField(
            controller: _nameController,
            textCapitalization: TextCapitalization.sentences,
            decoration: const InputDecoration(
              labelText: 'Service name',
              hintText: 'e.g. Haircut & styling',
            ),
            validator: (v) =>
                (v == null || v.trim().isEmpty) ? 'Required' : null,
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: _priceController,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              labelText: 'Price (AED)',
              prefixIcon: Icon(Icons.payments_outlined),
            ),
            validator: (v) {
              final parsed = Money.tryParseAed(v ?? '');
              if (parsed == null || parsed.isZero) return 'Enter a price';
              return null;
            },
          ),
          const SizedBox(height: 20),
          const Text('Duration',
              style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            children: [
              for (final minutes in durations)
                ChoiceChip(
                  label: Text(Formatters.duration(minutes)),
                  selected: _durationMinutes == minutes,
                  onSelected: (_) =>
                      setState(() => _durationMinutes = minutes),
                ),
            ],
          ),
          const SizedBox(height: 24),
          PrimaryButton(
            label: widget.existing == null ? 'Add service' : 'Save changes',
            loading: _submitting,
            onPressed: _submit,
          ),
        ],
      ),
    );
  }
}
