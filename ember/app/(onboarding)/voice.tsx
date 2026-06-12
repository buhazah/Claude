import { useState } from "react";
import { View, Text, Pressable, StyleSheet, Alert } from "react-native";
import { Audio } from "expo-av";
import { useRouter } from "expo-router";
import { supabase } from "@/lib/supabase";
import { colors, spacing } from "@/theme";

const QUESTIONS = [
  "What does a perfect Sunday look like for you?",
  "Describe someone you genuinely admire and why.",
  "What are you hoping to find here that you haven't found on other apps?",
];
const MIN_SEC = 20, MAX_SEC = 90, MAX_RETAKES = 3;

export default function VoiceOnboarding() {
  const [step, setStep] = useState(0);
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [retakes, setRetakes] = useState(0);
  const [paths, setPaths] = useState<string[]>([]);
  const router = useRouter();

  const start = async () => {
    const perm = await Audio.requestPermissionsAsync();
    if (!perm.granted) return Alert.alert("Microphone needed", "Voice answers are how Ember gets to know you.");
    await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
    const { recording } = await Audio.Recording.createAsync(
      Audio.RecordingOptionsPresets.HIGH_QUALITY,
      (status) => setElapsed(Math.floor((status.durationMillis ?? 0) / 1000)),
    );
    setRecording(recording);
  };

  const stop = async () => {
    if (!recording) return;
    await recording.stopAndUnloadAsync();
    const uri = recording.getURI()!;
    setRecording(null);
    if (elapsed < MIN_SEC) {
      if (retakes + 1 >= MAX_RETAKES) return Alert.alert("Keep going", "Answers need at least 20 seconds — take your time.");
      setRetakes(retakes + 1);
      return Alert.alert("A bit short", `Aim for ${MIN_SEC}–${MAX_SEC} seconds. ${MAX_RETAKES - retakes - 1} retakes left.`);
    }
    const { data: { user } } = await supabase.auth.getUser();
    const path = `${user!.id}/answer-${step}.m4a`;
    const file = await fetch(uri).then((r) => r.arrayBuffer());
    const { error } = await supabase.storage.from("voice").upload(path, file, {
      contentType: "audio/m4a", upsert: true,
    });
    if (error) return Alert.alert("Upload failed", error.message);

    const next = [...paths, path];
    setPaths(next);
    setElapsed(0);
    setRetakes(0);
    if (step < 2) setStep(step + 1);
    else router.push({ pathname: "/(onboarding)/intent", params: { audio_paths: JSON.stringify(next) } });
  };

  return (
    <View style={s.wrap}>
      <Text style={s.progress}>Question {step + 1} of 3</Text>
      <Text style={s.question}>{QUESTIONS[step]}</Text>
      <Text style={s.hint}>Speak for 20–90 seconds. There's no wrong answer.</Text>
      <Text style={s.timer}>{recording ? `${elapsed}s` : " "}</Text>
      <Pressable
        style={[s.mic, recording && s.micActive]}
        onPress={recording ? stop : start}
        disabled={recording !== null && elapsed >= MAX_SEC}
      >
        <Text style={s.micText}>{recording ? "Stop" : "🎙️ Record"}</Text>
      </Pressable>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, justifyContent: "center", padding: spacing.l, backgroundColor: colors.bg },
  progress: { color: colors.ember, fontWeight: "700", textAlign: "center" },
  question: { color: colors.text, fontSize: 26, fontWeight: "700", textAlign: "center", marginTop: spacing.m },
  hint: { color: colors.textDim, textAlign: "center", marginTop: spacing.s },
  timer: { color: colors.emberSoft, fontSize: 32, textAlign: "center", marginVertical: spacing.l, fontVariant: ["tabular-nums"] },
  mic: { backgroundColor: colors.ember, borderRadius: 100, padding: spacing.l, alignItems: "center", alignSelf: "center", minWidth: 160 },
  micActive: { backgroundColor: colors.card, borderWidth: 2, borderColor: colors.ember },
  micText: { color: colors.text, fontWeight: "700", fontSize: 18 },
});
