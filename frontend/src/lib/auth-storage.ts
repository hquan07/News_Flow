export type CachedUser = {
  email: string;
  role?: string;
  [key: string]: unknown;
};

export function readCachedUser(): CachedUser | null {
  const rawUser = localStorage.getItem("user_cache");
  if (!rawUser) return null;

  try {
    const user: unknown = JSON.parse(rawUser);
    if (
      user &&
      typeof user === "object" &&
      typeof (user as { email?: unknown }).email === "string"
    ) {
      return user as CachedUser;
    }
  } catch {
    // Invalid browser state is handled by clearing it below.
  }

  localStorage.removeItem("token");
  localStorage.removeItem("user_cache");
  return null;
}
