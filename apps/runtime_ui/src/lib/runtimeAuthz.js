export function hasRuntimeAdminRole(roles) {
  const normalizedRoles = new Set(
    (Array.isArray(roles) ? roles : [])
      .map((role) => String(role || "").trim().toLowerCase())
      .filter(Boolean),
  );

  return normalizedRoles.has("admin") || normalizedRoles.has("runtime:admin");
}
