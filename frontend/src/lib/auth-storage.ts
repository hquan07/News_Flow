export type CachedUser = {
  id?: string;
  email: string;
  role?: string;
  permissions?: string[];
  [key: string]: unknown;
};

const ROLE_PERMISSIONS: Record<string, string[]> = {
  user: ["dashboard.read", "reports.export"],
  analyst: ["dashboard.read", "reports.export", "reports.export_full"],
  operator: [
    "dashboard.read",
    "reports.export",
    "alerts.read",
    "alerts.manage",
    "crawler.read",
    "crawler.run",
    "system.read",
  ],
  admin: [
    "dashboard.read",
    "reports.export",
    "reports.export_full",
    "alerts.read",
    "alerts.manage",
    "crawler.read",
    "crawler.run",
    "system.read",
    "users.manage",
    "audit.read",
    "mock_data.create",
  ],
};

export function hasPermission(
  user: CachedUser | null,
  permission: string,
): boolean {
  if (!user) return false;
  const permissions = Array.isArray(user.permissions)
    ? user.permissions
    : ROLE_PERMISSIONS[user.role ?? "user"] ?? [];
  return permissions.includes(permission);
}

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
      const cachedUser = user as CachedUser;
      return {
        ...cachedUser,
        permissions:
          Array.isArray(cachedUser.permissions)
            ? cachedUser.permissions
            : ROLE_PERMISSIONS[cachedUser.role ?? "user"] ?? [],
      };
    }
  } catch {
    // Invalid browser state is handled by clearing it below.
  }

  localStorage.removeItem("token");
  localStorage.removeItem("user_cache");
  return null;
}
