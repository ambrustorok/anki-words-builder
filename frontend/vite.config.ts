import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const allowedHostsEnv = env.VITE_ALLOWED_HOSTS?.split(",")
    .map((host) => host.trim())
    .filter(Boolean);
  const devPort = Number(env.VITE_DEV_PORT || 5173);
  const proxyTarget = env.VITE_API_PROXY_TARGET || "http://backend:8100";

  return {
    plugins: [react()],
    server: {
      host: true,
      port: devPort,
      allowedHosts: allowedHostsEnv && allowedHostsEnv.length > 0 ? allowedHostsEnv : true,
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
          secure: false
        }
      }
    }
  };
});
