import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const allowedHostsEnv = env.VITE_ALLOWED_HOSTS?.split(",")
    .map((host) => host.trim())
    .filter(Boolean);

  return {
    plugins: [react()],
    server: {
      host: true,
      port: 5173,
      allowedHosts: allowedHostsEnv && allowedHostsEnv.length > 0 ? allowedHostsEnv : true
    }
  };
});
