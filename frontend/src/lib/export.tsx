import { createContext, ReactNode, useContext, useEffect, useRef, useState } from "react";

import { downloadApiFile } from "./api";

const ExportContext = createContext<{ exporting: boolean; exportDeck: (path: string, label: string, filename: string) => Promise<void> } | null>(null);

export function ExportProvider({ children }: { children: ReactNode }) {
  const [label, setLabel] = useState<string | null>(null);
  const exportingRef = useRef(false);
  const exporting = label !== null;

  useEffect(() => {
    if (!exporting) return;
    const preventUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    const preventClick = (event: MouseEvent) => {
      event.preventDefault();
      event.stopImmediatePropagation();
    };
    const preventBack = () => window.history.go(1);
    document.addEventListener("click", preventClick, true);
    window.addEventListener("beforeunload", preventUnload);
    window.addEventListener("popstate", preventBack);
    return () => {
      document.removeEventListener("click", preventClick, true);
      window.removeEventListener("beforeunload", preventUnload);
      window.removeEventListener("popstate", preventBack);
      if (window.history.state?.deckExport) window.history.back();
    };
  }, [exporting]);

  const exportDeck = async (path: string, nextLabel: string, filename: string) => {
    if (exportingRef.current) return;
    exportingRef.current = true;
    // Keep a same-URL history entry so the browser Back button stays on this page.
    window.history.pushState({ ...window.history.state, deckExport: true }, "", window.location.href);
    setLabel(nextLabel);
    try {
      await downloadApiFile(path, filename);
    } finally {
      exportingRef.current = false;
      setLabel(null);
    }
  };

  return (
    <ExportContext.Provider value={{ exporting, exportDeck }}>
      {exporting && (
        <div className="fixed inset-x-0 top-0 z-[60] bg-brand px-4 py-2 text-center text-sm font-semibold text-slate-900 shadow" role="status">
          {label} is being prepared. Please keep this page open.
          <span className="absolute inset-x-0 bottom-0 h-1 overflow-hidden bg-slate-900/15"><span className="block h-full w-1/3 animate-[pulse_1s_ease-in-out_infinite] bg-slate-900" /></span>
        </div>
      )}
      {children}
    </ExportContext.Provider>
  );
}

export function useDeckExport() {
  const context = useContext(ExportContext);
  if (!context) throw new Error("useDeckExport must be used within ExportProvider");
  return context;
}
