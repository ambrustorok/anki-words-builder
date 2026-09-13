import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { registerSW } from "virtual:pwa-register";

import App from "./App";
import "./index.css";

// Register service worker — auto-updates when a new version is deployed
const updateSW = registerSW({
  immediate: true,
  onNeedRefresh() {
    if (confirm("New version available. Reload?")) updateSW(true);
  },
  onOfflineReady() {
    console.log("App ready for offline use");
  },
});

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
