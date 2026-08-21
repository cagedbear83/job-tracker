import { useEffect } from "react";
import { useAuth } from "@clerk/clerk-react";
import { setTokenGetter } from "@/lib/api";

/**
 * Hands Clerk's session-token getter to the axios layer.
 *
 * Clerk exposes getToken() only through a hook, but lib/api.js is a plain
 * module used by every page. This component bridges the two: it renders
 * nothing and exists purely for the side effect of registering the getter
 * once, inside ClerkProvider.
 */
export default function ClerkTokenBridge() {
  const { getToken } = useAuth();

  useEffect(() => {
    setTokenGetter(getToken);
    return () => setTokenGetter(null);
  }, [getToken]);

  return null;
}
