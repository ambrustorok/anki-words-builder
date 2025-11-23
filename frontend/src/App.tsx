import { Routes, Route, Navigate } from "react-router-dom";

import { Layout } from "./components/Layout";
import { LoadingScreen } from "./components/LoadingScreen";
import { SessionProvider, useSession } from "./lib/session";
import { ThemeProvider } from "./lib/theme";
import { DashboardPage } from "./pages/DashboardPage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { ProfilePage } from "./pages/ProfilePage";
import { DeckListPage } from "./pages/DeckListPage";
import { DeckDetailPage } from "./pages/DeckDetailPage";
import { DeckEditorPage } from "./pages/DeckEditorPage";
import { CardCreatePage } from "./pages/CardCreatePage";
import { CardEditPage } from "./pages/CardEditPage";
import { AdminUsersPage } from "./pages/AdminUsersPage";
import { AdminUserDetailPage } from "./pages/AdminUserDetailPage";

function AppRoutes() {
  const session = useSession();
  if (session.isLoading) {
    return <LoadingScreen label="Loading session" />;
  }
  if (session.error) {
    return (
      <div className="p-6 text-center text-red-500">
        Failed to load session: {(session.error as Error).message}
      </div>
    );
  }
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/decks" element={<DeckListPage />} />
        <Route path="/decks/new" element={<DeckEditorPage mode="create" />} />
        <Route path="/decks/:deckId" element={<DeckDetailPage />} />
        <Route path="/decks/:deckId/edit" element={<DeckEditorPage mode="edit" />} />
        <Route path="/cards/new/:deckId" element={<CardCreatePage />} />
        <Route path="/cards/:groupId/edit" element={<CardEditPage />} />
        <Route path="/admin/users" element={<AdminUsersPage />} />
        <Route path="/admin/users/:userId" element={<AdminUserDetailPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <SessionProvider>
        <AppRoutes />
      </SessionProvider>
    </ThemeProvider>
  );
}
