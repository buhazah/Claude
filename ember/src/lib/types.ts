export type Intent = "long_term" | "open_to_long_term" | "figuring_it_out";

export interface Profile {
  id: string;
  first_name: string;
  age: number;
  city: string;
  occupation_category: string | null;
  photos: string[];
  bio: string | null;
  intent: Intent | null;
  intent_statement: string | null;
  verified: boolean;
  trust_score: number;
  reliability_score: number;
  voice_clips: string[];
}

export interface DailyMatch {
  id: string;
  user_a: string;
  user_b: string;
  compat_score: number;
  compat_reasons: string[];
  status: "pending" | "connected" | "passed" | "expired";
  expires_at: string;
  other?: Profile;
}

export interface Message {
  id: string;
  conversation_id: string;
  sender: string | null;
  body: string;
  is_coach_nudge: boolean;
  created_at: string;
}

export interface Conversation {
  id: string;
  match_id: string;
  user_a: string;
  user_b: string;
  status: string;
  last_message_at: string | null;
  date_verified: boolean;
  other?: Profile;
}

export interface DateIdea {
  venue_name: string;
  venue_type: string;
  why_it_fits: string;
  suggested_time: string;
  difficulty: "easy" | "medium" | "adventurous";
}
