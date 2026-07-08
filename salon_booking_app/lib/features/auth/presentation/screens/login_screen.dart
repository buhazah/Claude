import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/router/route_names.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/widgets/primary_button.dart';
import '../controllers/auth_controller.dart';
import '../widgets/auth_feedback_listener.dart';

/// Entry screen: phone number (primary) with an email fallback link.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _phoneController = TextEditingController(text: '+971');

  @override
  void dispose() {
    _phoneController.dispose();
    super.dispose();
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    ref
        .read(authControllerProvider.notifier)
        .sendOtp(_phoneController.text.trim());
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authControllerProvider);

    // Navigate to OTP entry once the code has been sent.
    ref.listen(authControllerProvider, (previous, next) {
      if (previous?.verificationId == null && next.verificationId != null) {
        context.push(RouteNames.otp);
      }
    });
    listenForAuthFeedback(context, ref);

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Icon(Icons.spa_rounded,
                      size: 64, color: AppColors.primary),
                  const SizedBox(height: 16),
                  Text(
                    AppConstants.appName,
                    textAlign: TextAlign.center,
                    style: Theme.of(context)
                        .textTheme
                        .headlineMedium
                        ?.copyWith(fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Book your next salon visit in seconds.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: AppColors.textSecondary),
                  ),
                  const SizedBox(height: 40),
                  TextFormField(
                    controller: _phoneController,
                    keyboardType: TextInputType.phone,
                    decoration: const InputDecoration(
                      labelText: 'Phone number',
                      hintText: '+971 50 123 4567',
                      prefixIcon: Icon(Icons.phone_rounded),
                    ),
                    validator: (value) {
                      final v = value?.trim() ?? '';
                      if (v.length < 9 || !v.startsWith('+')) {
                        return 'Enter a valid phone number with country code';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 20),
                  PrimaryButton(
                    label: 'Continue with phone',
                    loading: auth.submitting,
                    onPressed: _submit,
                  ),
                  const SizedBox(height: 16),
                  TextButton(
                    onPressed: () => context.push(RouteNames.emailLogin),
                    child: const Text('Use email instead'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
