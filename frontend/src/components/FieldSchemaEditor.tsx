import { useState } from "react";

export interface FieldOption {
  key: string;
  label: string;
  description?: string;
  required?: boolean;
  supports_generation?: boolean;
  default_auto_generate?: boolean;
}

export interface FieldSchemaEntry {
  key: string;
  label: string;
  description?: string;
  required?: boolean;
  auto_generate?: boolean;
}

interface Props {
  options: FieldOption[];
  schema: FieldSchemaEntry[];
  onChange: (schema: FieldSchemaEntry[]) => void;
}

export function FieldSchemaEditor({ options, schema, onChange }: Props) {
  const [customField, setCustomField] = useState({ key: "", label: "", description: "" });

  const schemaMap = new Map(schema.map((entry) => [entry.key, entry]));

  const toggleField = (option: FieldOption, enabled: boolean) => {
    if (option.required && !enabled) return;
    const next = new Map(schemaMap);
    if (enabled) {
      next.set(option.key, {
        key: option.key,
        label: option.label,
        description: option.description,
        required: option.required,
        auto_generate:
          schemaMap.get(option.key)?.auto_generate ?? option.default_auto_generate ?? false
      });
    } else {
      next.delete(option.key);
    }
    onChange(Array.from(next.values()));
  };

  const setAuto = (option: FieldOption, enabled: boolean) => {
    const next = schema.map((entry) =>
      entry.key === option.key ? { ...entry, auto_generate: enabled } : entry
    );
    onChange(next);
  };

  const addCustomField = () => {
    const key = customField.key.trim();
    const label = customField.label.trim() || key;
    if (!key) return;
    if (schemaMap.has(key)) return;
    const next = [...schema, { key, label, description: customField.description, required: false, auto_generate: false }];
    onChange(next);
    setCustomField({ key: "", label: "", description: "" });
  };

  const removeCustomField = (key: string) => {
    const next = schema.filter((entry) => entry.key !== key);
    onChange(next);
  };

  const customEntries = schema.filter((entry) => !options.some((opt) => opt.key === entry.key));

  return (
    <div className="space-y-4">
      {options.map((option) => {
        const enabled = schemaMap.has(option.key) || option.required;
        const entry = schemaMap.get(option.key);
        return (
          <div key={option.key} className="rounded-xl border border-slate-200 bg-white px-4 py-3 dark:border-slate-700 dark:bg-slate-900">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-slate-900 dark:text-white">{option.label}</p>
                {option.description && <p className="text-xs text-slate-500 dark:text-slate-400">{option.description}</p>}
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                <input
                  type="checkbox"
                  checked={enabled}
                  disabled={option.required}
                  onChange={(event) => toggleField(option, event.target.checked)}
                />
                <span>{option.required ? "Required" : "Enabled"}</span>
              </label>
            </div>
            {enabled && option.supports_generation && (
              <label className="mt-2 flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                <input
                  type="checkbox"
                  checked={entry?.auto_generate ?? true}
                  onChange={(event) => setAuto(option, event.target.checked)}
                />
                Auto-generate content
              </label>
            )}
          </div>
        );
      })}

      <div className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-4 dark:border-slate-600 dark:bg-slate-900">
        <p className="text-sm font-semibold text-slate-900 dark:text-white">Custom fields</p>
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          <input
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
            placeholder="Key"
            value={customField.key}
            onChange={(event) => setCustomField((prev) => ({ ...prev, key: event.target.value }))}
          />
          <input
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
            placeholder="Label"
            value={customField.label}
            onChange={(event) => setCustomField((prev) => ({ ...prev, label: event.target.value }))}
          />
          <input
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
            placeholder="Description"
            value={customField.description}
            onChange={(event) => setCustomField((prev) => ({ ...prev, description: event.target.value }))}
          />
        </div>
        <button
          type="button"
          className="mt-3 rounded-full bg-brand px-4 py-2 text-sm font-semibold text-slate-900"
          onClick={addCustomField}
        >
          Add field
        </button>

        {customEntries.length > 0 && (
          <ul className="mt-3 space-y-2">
            {customEntries.map((entry) => (
              <li
                key={entry.key}
                className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700"
              >
                <div>
                  <p className="font-medium text-slate-900 dark:text-white">{entry.label}</p>
                  {entry.description && <p className="text-xs text-slate-500 dark:text-slate-400">{entry.description}</p>}
                </div>
                <button type="button" className="text-xs text-red-500" onClick={() => removeCustomField(entry.key)}>
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
