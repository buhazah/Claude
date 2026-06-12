import { useState } from "react";
import { View, Text, TextInput, Pressable, StyleSheet, Alert } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { supabase } from "@/lib/supabase";
import { colors, spacing } from "@/theme";

export default function Otp() {
  const { phone } = useLocalSearchParams<{ phone: string }>();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  const verify = async () => {
    setBusy(true);
    const { error } = await supabase.auth.verifyOtp({ phone: phone!, token: code, type: "sms" });
    setBusy(false);
    if (error) return Alert.alert("Invalid code", error.message);
    router.replace("/(onboarding)/verify-identity");
  };

  return (
    <View style={s.wrap}>
      <Text style={s.title}>Enter the 6-digit code</Text>
      <Text style={s.sub}>Sent to {phone}. Expires in 5 minutes.</Text>
      <TextInput
        style={s.input}
        keyboardType="number-pad"
        maxLength={6}
        autoFocus
        value={code}
        onChangeText={setCode}
        placeholder="••••••"
        placeholderTextColor={colors.textDim}
      />
      <Pressable style={[s.btn, busy && { opacity: 0.6 }]} disabled={busy || code.length !== 6} onPress={verify}>
        <Text style={s.btnText}>Verify</Text>
      </Pressable>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, justifyContent: "center", padding: spacing.l, backgroundColor: colors.bg },
  title: { color: colors.text, fontSize: 24, fontWeight: "700" },
  sub: { color: colors.textDim, marginTop: spacing.s, marginBottom: spacing.l },
  input: { backgroundColor: colors.card, color: colors.text, borderRadius: 14, padding: spacing.m, fontSize: 28, letterSpacing: 12, textAlign: "center", borderWidth: 1, borderColor: colors.border },
  btn: { backgroundColor: colors.ember, borderRadius: 14, padding: spacing.m, alignItems: "center", marginTop: spacing.l },
  btnText: { color: "#fff", fontWeight: "700", fontSize: 16 },
});
