interface DeckSummary {
  id?: string;
  name?: string;
  updated_at?: string;
  entry_count?: number;
  card_count?: number;
  anki_id?: string;
}

interface ConflictOption {
  policy: string;
  label: string;
  description?: string;
}

export interface DeckImportConflictPayload {
  code: string;
  message: string;
  existingDeck: DeckSummary;
  incomingDeck: DeckSummary;
  options: ConflictOption[];
}

interface ImportConflictModalProps {
  payload: DeckImportConflictPayload;
  isSubmitting: boolean;
  onSelect: (policy: string) => void;
  onCancel: () => void;
}

function formatTimestamp(value?: string) {
  if (!value) return "Unknown";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function ImportConflictModal({ payload, isSubmitting, onSelect, onCancel }: ImportConflictModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm">
      <div className="w-full max-w-xl rounded-2xl bg-white p-6 shadow-2xl dark:bg-slate-900">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Deck conflict detected</h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{payload.message}</p>
          </div>
          <button
            type="button"
            aria-label="Close"
            className="text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300"
            onClick={onCancel}
          >
            <span aria-hidden="true">x</span>
          </button>
        </div>
        <div className="mt-4 grid gap-3 rounded-2xl border border-slate-200 p-4 dark:border-slate-800">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Existing deck</p>
              <p className="font-semibold text-slate-900 dark:text-white">{payload.existingDeck.name || "Unnamed deck"}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">Updated {formatTimestamp(payload.existingDeck.updated_at)}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Incoming deck</p>
              <p className="font-semibold text-slate-900 dark:text-white">{payload.incomingDeck.name || "Unnamed deck"}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Updated {formatTimestamp(payload.incomingDeck.updated_at)}
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 rounded-xl bg-slate-50 p-3 text-xs text-slate-600 dark:bg-slate-800/60 dark:text-slate-300">
            <div>
              <p className="font-semibold">{payload.incomingDeck.entry_count ?? 0}</p>
              <p>Entries detected in backup</p>
            </div>
            <div>
              <p className="font-semibold">{payload.incomingDeck.card_count ?? 0}</p>
              <p>Cards detected in backup</p>
            </div>
          </div>
        </div>
        <div className="mt-5 space-y-3">
          {payload.options.map((option) => (
            <button
              key={option.policy}
              type="button"
              className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-left transition hover:border-brand hover:bg-brand/10 disabled:opacity-60 dark:border-slate-700 dark:hover:border-brand"
              onClick={() => onSelect(option.policy)}
              disabled={isSubmitting}
            >
              <p className="font-semibold text-slate-900 dark:text-white">{option.label}</p>
              {option.description && <p className="text-sm text-slate-500 dark:text-slate-400">{option.description}</p>}
            </button>
          ))}
        </div>
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            className="rounded-full border border-slate-300 px-4 py-2 text-sm text-slate-600 transition hover:border-slate-400 dark:border-slate-700 dark:text-slate-300"
            onClick={onCancel}
            disabled={isSubmitting}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
