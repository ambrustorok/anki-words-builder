const CLOUDFLARE_LOGOUT_PATH = "/cdn-cgi/access/logout";

/**
 * Builds the Cloudflare Access logout URL for the current origin.
 * Falls back to just the path during SSR or testing.
 */
export function getCloudflareLogoutUrl() {
  if (typeof window === "undefined") {
    return CLOUDFLARE_LOGOUT_PATH;
  }
  return `${window.location.origin}${CLOUDFLARE_LOGOUT_PATH}`;
}
