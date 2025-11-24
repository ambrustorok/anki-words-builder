import { Link } from "react-router-dom";

const CARD_VARIABLES = [
  { token: "{{foreign_phrase}}", description: "Foreign expression captured from the form." },
  { token: "{{native_phrase}}", description: "Learner’s native-language translation (if provided)." },
  { token: "{{dictionary_entry}}", description: "Dictionary/notes field, often HTML." },
  { token: "{{example_sentence}}", description: "Example sentence in the deck’s target language." },
  { token: "{{direction}}", description: "Either “forward” or “backward”, helpful for conditional styling." },
  { token: "{{target_language}}", description: "Deck target language, e.g. “Spanish”." },
  { token: "{{native_language}}", description: "Learner’s native language from onboarding." },
  { token: "{{custom_field_key}}", description: "Any custom fields you enable in the schema use their key." }
];

const AUDIO_PLACEHOLDERS = [
  { token: "{target_language}", description: "Replaced with the deck’s target language inside audio instructions." }
];

export function HelpPage() {
  return (
    <div className="space-y-8">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Template help</h1>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
          Card templates and audio prompts accept lightweight templating so you can surface any field and describe how
          cards should look. Variables are written in <code className="rounded bg-slate-100 px-1 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-200">{"{{double_curly_braces}}"}</code>{" "}
          for cards and <code className="rounded bg-slate-100 px-1 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-200">{"{single_curly_braces}"}</code> for audio instructions.
        </p>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
          Ready to experiment? Open any deck, hit <Link to="/decks" className="font-semibold text-brand underline">Edit deck</Link>, and
          adjust the card templates or audio instructions from there.
        </p>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Card variables</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Every card template receives the values you enter on the form plus a few contextual helpers. The table lists
          the most common placeholders—custom fields use their schema key.
        </p>
        <dl className="mt-4 divide-y divide-slate-100 dark:divide-slate-800">
          {CARD_VARIABLES.map((entry) => (
            <div key={entry.token} className="flex flex-col gap-1 py-3 sm:flex-row sm:items-center sm:justify-between">
              <dt className="font-mono text-sm text-slate-900 dark:text-slate-100">{entry.token}</dt>
              <dd className="text-sm text-slate-500 dark:text-slate-300">{entry.description}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-4 rounded-2xl border border-slate-100 bg-slate-50 p-4 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-300">
          <p className="font-semibold text-slate-900 dark:text-white">Tip</p>
          <p className="mt-1">
            You can include HTML tags (like <code>&lt;div&gt;</code>, <code>&lt;b&gt;</code>, or <code>&lt;i&gt;</code>)
            inside templates. Make sure to keep the markup lightweight for readability on cards.
          </p>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Audio placeholders</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Audio instructions support simple string replacement. The placeholders below are wrapped in single braces.
        </p>
        <dl className="mt-4 divide-y divide-slate-100 dark:divide-slate-800">
          {AUDIO_PLACEHOLDERS.map((entry) => (
            <div key={entry.token} className="flex flex-col gap-1 py-3 sm:flex-row sm:items-center sm:justify-between">
              <dt className="font-mono text-sm text-slate-900 dark:text-slate-100">{entry.token}</dt>
              <dd className="text-sm text-slate-500 dark:text-slate-300">{entry.description}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
