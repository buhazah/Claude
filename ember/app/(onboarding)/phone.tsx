import { useState } from "react";
import { View, Text, TextInput, Pressable, StyleSheet, Alert, Switch } from "react-native";
import { useRouter } from "expo-router";
import { supabase } from "@/lib/supabase";
import { colors, spacing } from "@/theme";

export default function Phone() {
  const [phone, setPhone] = useState("");
  const [isAdult, setIsAdult] = useState(false);
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  const sendOtp = async () => {
    if (!isAdult) return Alert.alert("Ember is 18+", "You must confirm you are 18 or older.");
    setBusy(true);
    const { error } = await supabase.auth.signInWithOtp({ phone });
    setBusy(false);
    if (error) return Alert.alert("Couldn't send code", error.message);
    router.push({ pathname: "/(onboarding)/otp", params: { phone } });
  };

  return (
    <View style={s.wrap}>
      <Text style={s.logo}>🔥 Ember</Text>
      <Text style={s.tagline}>Date with intent.</Text>
      <Text style={s.label}>Phone number</Text>
      <TextInput
        style={s.input}
        keyboardType="phone-pad"
        autoComplete="tel"
        placeholder="+1 512 555 0100"
        placeholderTextColor={colors.textDim}
        value={phone}
        onChangeText={setPhone}
      />
      <View style={s.ageRow}>
        <Switch value={isAdult} onValueChange={setIsAdult} trackColor={{ true: colors.ember }} />
        <Text style={s.ageText}>I confirm I am 18 or older</Text>
      </View>
      <Pressable style={[s.btn, busy && s.btnDim]} onPress={sendOtp} disabled={busy}>
        <Text style={s.btnText}>{busy ? "Sending…" : "Send code"}</Text>
      </Pressable>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, justifyContent: "center", padding: spacing.l, backgroundColor: colors.bg },
  logo: { fontSize: 40, fontWeight: "800", color: colors.text, textAlign: "center" },
  tagline: { color: colors.emberSoft, textAlign: "center", marginBottom: spacing.xl, fontSize: 16 },
  label: { color: colors.textDim, marginBottom: spacing.s },
  input: { backgroundColor: colors.card, color: colors.text, borderRadius: 14, padding: spacing.m, fontSize: 18, borderWidth: 1, borderColor: colors.border },
  ageRow: { flexDirection: "row", alignItems: "center", gap: spacing.m, marginVertical: spacing.l },
  ageText: { color: colors.text },
  btn: { backgroundColor: colors.ember, borderRadius: 14, padding: spacing.m, alignItems: "center" },
  btnDim: { opacity: 0.6 },
  btnText: { color: "#fff", fontWeight: "700", fontSize: 16 },
});
