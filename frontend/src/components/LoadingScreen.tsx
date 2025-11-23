export function LoadingScreen({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex min-h-[50vh] items-center justify-center text-slate-500 dark:text-slate-300">
      <div className="mr-4 h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand dark:border-slate-700" />
      <span>{label}…</span>
    </div>
  );
}
