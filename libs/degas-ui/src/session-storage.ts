const OWNER_KEY = "degas_owner_tokens";

export function setOwnerToken(id: string, token: string): void {
  try {
    const map = JSON.parse(localStorage.getItem(OWNER_KEY) ?? "{}");
    map[id] = token;
    localStorage.setItem(OWNER_KEY, JSON.stringify(map));
  } catch { /* empty */ }
}

export function getOwnerToken(id: string): string | null {
  try {
    const map = JSON.parse(localStorage.getItem(OWNER_KEY) ?? "{}");
    return map[id] ?? null;
  } catch {
    return null;
  }
}

export function removeOwnerToken(id: string): void {
  try {
    const map = JSON.parse(localStorage.getItem(OWNER_KEY) ?? "{}");
    delete map[id];
    localStorage.setItem(OWNER_KEY, JSON.stringify(map));
  } catch { /* empty */ }
}
