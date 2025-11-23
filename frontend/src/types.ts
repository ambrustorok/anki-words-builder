export interface DeckField {
  key: string;
  label: string;
  description?: string;
  required?: boolean;
  auto_generate?: boolean;
}

export interface Deck {
  id: string;
  name: string;
  target_language: string;
  field_schema: DeckField[];
  prompt_templates?: Record<string, unknown>;
}

export interface CardDirection {
  id: string;
  direction: "forward" | "backward";
  front: string;
  back: string;
  has_front_audio?: boolean;
  has_back_audio?: boolean;
}

export interface CardGroup {
  group_id: string;
  payload: Record<string, string>;
  directions: CardDirection[];
  created_at?: string;
  updated_at?: string;
}

export interface DeckDetailResponse {
  deck: Deck;
  cards: CardGroup[];
  entryCount: number;
  cardCount: number;
  lastModified?: string;
  generationPrompts: Record<string, unknown>;
}
