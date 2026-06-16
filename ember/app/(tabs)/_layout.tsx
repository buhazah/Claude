import { Tabs } from "expo-router";
import { Text } from "react-native";
import { colors } from "@/theme";

const icon = (glyph: string) => ({ color }: { color: string }) => (
  <Text style={{ fontSize: 22, color }}>{glyph}</Text>
);

export default function TabsLayout() {
  return (
    <Tabs screenOptions={{
      headerStyle: { backgroundColor: colors.bg },
      headerTintColor: colors.text,
      tabBarStyle: { backgroundColor: colors.card, borderTopColor: colors.border },
      tabBarActiveTintColor: colors.ember,
      tabBarInactiveTintColor: colors.textDim,
      sceneStyle: { backgroundColor: colors.bg },
    }}>
      <Tabs.Screen name="index" options={{ title: "Matches", tabBarIcon: icon("🔥") }} />
      <Tabs.Screen name="chat" options={{ title: "Chat", tabBarIcon: icon("💬") }} />
      <Tabs.Screen name="dates" options={{ title: "Dates", tabBarIcon: icon("📅") }} />
      <Tabs.Screen name="profile" options={{ title: "Profile", tabBarIcon: icon("👤") }} />
    </Tabs>
  );
}
