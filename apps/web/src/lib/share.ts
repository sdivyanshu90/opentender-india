import { assetUrl } from "./data";

/** Absolute, shareable URL of Discover with the given URL params. */
export function discoverUrl(query: string): string {
  return new URL(assetUrl(`discover${query ? `?${query}` : ""}`), window.location.origin).toString();
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
