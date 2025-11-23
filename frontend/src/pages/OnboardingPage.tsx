import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSession } from "../lib/session";
import { apiFetch } from "../lib/api";

export function OnboardingPage() {
  const session = useSession();
  const [language, setLanguage] = useState(session.data?.user.nativeLanguage ?? "");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      await apiFetch("/session/native-language", {
        method: "POST",
        json: { nativeLanguage: language }
      });
      session.refetch();
      navigate("/");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <section className="mx-auto max-w-xl rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
      <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Pick your native language</h1>
      <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
        We use this once when generating translations so your decks stay consistent.
      </p>
      <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
        <label className="block text-sm font-medium text-slate-700">
          Native language
          <select
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"
            value={language}
            onChange={(event) => setLanguage(event.target.value)}
            required
          >
            <option value="">Select</option>
            {session.data?.nativeLanguageOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        {error && <p className="text-sm text-red-500">{error}</p>}
        <button type="submit" className="rounded-full bg-brand px-4 py-2 text-sm font-semibold text-slate-900">
          Save preference
        </button>
      </form>
    </section>
  );
}
