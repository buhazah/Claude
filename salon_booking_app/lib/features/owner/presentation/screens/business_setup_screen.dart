import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/errors/error_text.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/widgets/primary_button.dart';
import '../../../auth/presentation/controllers/auth_controller.dart';
import '../../../auth/presentation/providers/auth_providers.dart';
import '../../../businesses/domain/entities/business.dart';
import '../../../businesses/presentation/providers/business_providers.dart';
import '../providers/owner_providers.dart';

/// Create a business profile — shown as first-run onboarding (no business
/// yet) and pushed as a route when adding another branch.
///
/// Location defaults to the city center for the MVP; a map picker slots in
/// here later without touching the repository.
class BusinessSetupScreen extends ConsumerStatefulWidget {
  const BusinessSetupScreen({super.key});

  @override
  ConsumerState<BusinessSetupScreen> createState() =>
      _BusinessSetupScreenState();
}

class _BusinessSetupScreenState extends ConsumerState<BusinessSetupScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _descriptionController = TextEditingController();
  final _addressController = TextEditingController();
  final _cityController = TextEditingController(text: 'Dubai');
  Audience _audience = Audience.both;
  BusinessCategory _category = BusinessCategory.salon;
  bool _submitting = false;

  @override
  void dispose() {
    _nameController.dispose();
    _descriptionController.dispose();
    _addressController.dispose();
    _cityController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final user = ref.read(currentUserProvider).valueOrNull;
    if (user == null) return;

    setState(() => _submitting = true);
    try {
      final id = await ref.read(ownerActionsProvider).createBusiness(
            ownerId: user.id,
            name: _nameController.text.trim(),
            description: _descriptionController.text.trim(),
            address: _addressController.text.trim(),
            city: _cityController.text.trim(),
            audience: _audience,
            category: _category,
            latitude: AppConstants.defaultLatitude,
            longitude: AppConstants.defaultLongitude,
          );
      if (!mounted) return;
      // Make the new business the active one, then leave: pop when pushed
      // as "add branch"; when shown as the onboarding gate the owner shell
      // swaps to the dashboard on its own.
      ref.read(selectedBusinessIdProvider.notifier).select(id);
      if (Navigator.of(context).canPop()) Navigator.of(context).pop();
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
    return Scaffold(
      appBar: AppBar(
        title: const Text('Set up your salon'),
        actions: [
          if (!Navigator.of(context).canPop())
            TextButton(
              onPressed: () =>
                  ref.read(authControllerProvider.notifier).signOut(),
              child: const Text('Sign out'),
            ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'This is what customers will see when discovering you. '
                  'New listings are reviewed before going live.',
                  style: TextStyle(color: AppColors.textSecondary),
                ),
                const SizedBox(height: 20),
                TextFormField(
                  controller: _nameController,
                  textCapitalization: TextCapitalization.words,
                  decoration:
                      const InputDecoration(labelText: 'Business name'),
                  validator: (v) =>
                      (v == null || v.trim().isEmpty) ? 'Required' : null,
                ),
                const SizedBox(height: 14),
                TextFormField(
                  controller: _descriptionController,
                  maxLines: 3,
                  decoration: const InputDecoration(
                    labelText: 'Description',
                    hintText: 'What makes your place special?',
                  ),
                ),
                const SizedBox(height: 14),
                TextFormField(
                  controller: _addressController,
                  decoration: const InputDecoration(labelText: 'Address'),
                  validator: (v) =>
                      (v == null || v.trim().isEmpty) ? 'Required' : null,
                ),
                const SizedBox(height: 14),
                TextFormField(
                  controller: _cityController,
                  decoration: const InputDecoration(labelText: 'City'),
                  validator: (v) =>
                      (v == null || v.trim().isEmpty) ? 'Required' : null,
                ),
                const SizedBox(height: 20),
                const Text('Category',
                    style: TextStyle(fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final category in BusinessCategory.values)
                      ChoiceChip(
                        label: Text(category.label),
                        selected: _category == category,
                        onSelected: (_) =>
                            setState(() => _category = category),
                      ),
                  ],
                ),
                const SizedBox(height: 20),
                const Text('Clientele',
                    style: TextStyle(fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  children: [
                    for (final audience in Audience.values)
                      ChoiceChip(
                        label: Text(audience.label),
                        selected: _audience == audience,
                        onSelected: (_) =>
                            setState(() => _audience = audience),
                      ),
                  ],
                ),
                const SizedBox(height: 32),
                PrimaryButton(
                  label: 'Create business',
                  loading: _submitting,
                  onPressed: _submit,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
