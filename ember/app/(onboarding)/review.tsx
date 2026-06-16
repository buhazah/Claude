import { useState } from "react";
import { View, Text, TextInput, Pressable, StyleSheet, Alert } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import * as ImagePicker from "expo-image-picker";
import { supabase } from "@/lib/supabase";
import { colors, spacing } from "@/theme";

export default function Review() {
  const { bio: generated } = useLocalSearchParams<{ bio: string }>();
  const [bio, setBio] = useState(generated ?? "");
  const [photoCount, setPhotoCount] = useState(0);
  const router = useRouter();

  const addPhotos = async () => {
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"], allowsMultipleSelection: true, selectionLimit: 5, quality: 0.8,
    });
    if (res.canceled) return;
    const { data: { user } } = await supabase.auth.getUser();
    const paths: string[] = [];
    for (const [i, asset] of res.assets.entries()) {
      const path = `${user!.id}/photo-${i}.jpg`;
      const file = await fetch(asset.uri).then((r) => r.arrayBuffer());
      const { error } = await supabase.storage.from("photos").upload(path, file, {
        contentType: "image/jpeg", upsert: true,
      });
      if (!error) paths.push(supabase.storage.from("photos").getPublicUrl(path).data.publicUrl);
    }
    await supabase.from("profiles").update({ photos: paths }).eq("id", user!.id);
    setPhotoCount(paths.length);
  };

  const finish = async () => {
    if (photoCount === 0) return Alert.alert("Add at least one photo");
    const { data: { user } } = await supabase.auth.getUser();
    await supabase.from("profiles").update({ bio }).eq("id", user!.id);
    router.replace("/(tabs)");
  };

  return (
    <View style={s.wrap}>
      <Text style={s.title}>Here's how you sound</Text>
      <Text style={s.sub}>Written from your voice answers. Edit anything.</Text>
      <TextInput style={s.input} multiline maxLength={160} value={bio} onChangeText={setBio} />
      <Pressable style={s.secondary} onPress={addPhotos}>
        <Text style={s.secondaryText}>{photoCount ? `${photoCount} photos added ✓` : "Add photos (up to 5)"}</Text>
      </Pressable>
      <Pressable style={s.btn} onPress={finish}>
        <Text style={s.btnText}>Enter Ember 🔥</Text>
      </Pressable>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, justifyContent: "center", padding: spacing.l, backgroundColor: colors.bg },
  title: { color: colors.text, fontSize: 26, fontWeight: "700" },
  sub: { color: colors.textDim, marginTop: spacing.s, marginBottom: spacing.l },
  input: { backgroundColor: colors.card, color: colors.text, borderRadius: 14, padding: spacing.m, minHeight: 90, borderWidth: 1, borderColor: colors.border, fontSize: 16, textAlignVertical: "top" },
  secondary: { borderRadius: 14, padding: spacing.m, alignItems: "center", marginTop: spacing.l, borderWidth: 1, borderColor: colors.ember },
  secondaryText: { color: colors.ember, fontWeight: "600" },
  btn: { backgroundColor: colors.ember, borderRadius: 14, padding: spacing.m, alignItems: "center", marginTop: spacing.m },
  btnText: { color: "#fff", fontWeight: "700", fontSize: 16 },
});
