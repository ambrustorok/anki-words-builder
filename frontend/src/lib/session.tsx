import { createContext, useContext } from "react";
import { useQuery, UseQueryResult } from "@tanstack/react-query";

import { apiFetch } from "./api";

export interface SessionData {
  user: {
    id: string;
    nativeLanguage?: string | null;
    primaryEmail?: string | null;
    isAdmin: boolean;
  };
  logoutUrl: string;
  canGenerate: boolean;
  needsOnboarding: boolean;
  nativeLanguageOptions: string[];
  targetLanguageOptions: string[];
}

const SessionContext = createContext<UseQueryResult<SessionData> | null>(null);

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error("SessionContext unavailable");
  }
  return ctx;
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const query = useQuery({
    queryKey: ["session"],
    queryFn: () => apiFetch<SessionData>("/session"),
    staleTime: 60_000
  });
  return <SessionContext.Provider value={query}>{children}</SessionContext.Provider>;
}
