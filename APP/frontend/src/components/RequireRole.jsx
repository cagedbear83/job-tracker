// admin/RequireRole.jsx
// Cosmetic front-end gate. The backend enforces every action regardless — this
// just avoids rendering admin UI (and its lazy bundle) for unauthorized users.

const RANK = { user: 0, support_staff: 1, platform_admin: 2 };

export default function RequireRole({ atLeast = "support_staff", role, children, fallback = null }) {
  const ok = (RANK[role] ?? 0) >= (RANK[atLeast] ?? 99);
  return ok ? children : fallback;
}

// NOTE (integration): copied unchanged from admin_portal/RequireRole.jsx —
// this component is self-contained (no imports from the backend or other
// admin/ files), so no adaptation was needed.
