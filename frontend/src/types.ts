export interface DeckField {
  key: string;
  label: string;
  description?: string;
  required?: boolean;
  auto_generate?: boolean;
}

// ---------------------------------------------------------------------------
// Tags
// ---------------------------------------------------------------------------

/** A single tag definition belonging to a deck */
export interface DeckTag {
  id: string;
  deck_id?: string;
  name: string;
  category: string;
  color: string;
  sort_order: number;
  created_at?: string;
}

/** Tag mode controls how/whether tags work for a deck */
export type TagMode = "off" | "manual" | "auto";

/** A preset category returned from the API */
export interface TagPresetCategory {
  category: string;
  tags: { name: string; color: string }[];
}

export interface PromptFaceTemplate {
  front?: string;
  back?: string;
}

export interface PromptTemplates {
  forward?: PromptFaceTemplate;
  backward?: PromptFaceTemplate;
  generation?: Record<string, unknown>;
  audio?: {
    instructions?: string;
    enabled?: boolean;
  };
}

export interface Deck {
  id: string;
  name: string;
  target_language: string;
  field_schema: DeckField[];
  prompt_templates?: PromptTemplates;
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
  tags?: DeckTag[];
}

export interface DeckDetailResponse {
  deck: Deck;
  cards: CardGroup[];
  entryCount: number;
  cardCount: number;
  lastModified?: string;
  generationPrompts: Record<string, unknown>;
  tagMode?: TagMode;
  tagMulti?: boolean;
}
