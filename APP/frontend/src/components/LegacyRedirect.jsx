import { Navigate, useLocation } from "react-router-dom";

/**
 * Redirect that preserves the query string.
 *
 * <Navigate to="/sign-up"> silently drops search params, which would break the
 * pricing deep links from illinoisjobtracker.com — /register?plan=pro would
 * arrive at /sign-up with no idea which plan was chosen.
 */
export default function LegacyRedirect({ to }) {
  const { search, hash } = useLocation();
  return <Navigate to={`${to}${search}${hash}`} replace />;
}
