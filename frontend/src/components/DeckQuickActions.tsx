import { Link } from "react-router-dom";
import { API_BASE_URL } from "../lib/api";

interface Props {
  deckId: string;
}

export function DeckQuickActions({ deckId }: Props) {
  return (
    <div className="flex flex-wrap justify-end gap-3">
      <Link className="text-brand hover:underline" to={`/cards/new/${deckId}`}>
        Add cards
      </Link>
      <Link className="text-brand hover:underline" to={`/decks/${deckId}`}>
        View
      </Link>
      <Link className="text-brand hover:underline" to={`/decks/${deckId}/edit`}>
        Edit
      </Link>
      <a className="text-brand hover:underline" href={`${API_BASE_URL}/decks/${deckId}/export`}>
        Download
      </a>
    </div>
  );
}
