import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { SignUp as ClerkSignUp } from "@clerk/clerk-react";
import AuthSplitLayout from "@/components/AuthSplitLayout";
import { clerkAppearance } from "@/lib/clerkAppearance";

const VALID_PLANS = ["free", "pro", "caseworker"];
export const PLAN_STORAGE_KEY = "ijt-selected-plan";

export default function SignUp() {
  const [searchParams] = useSearchParams();

  // Clerk redirects to /onboarding on success and does not carry our query
  // params across, so stash the plan the visitor picked on the pricing page
  // before handing control over. sessionStorage, not localStorage: this is
  // scoped to finishing one signup, not remembered forever.
  useEffect(() => {
    const plan = searchParams.get("plan");
    if (plan && VALID_PLANS.includes(plan)) {
      try {
        sessionStorage.setItem(PLAN_STORAGE_KEY, plan);
      } catch {
        // Private mode — the plan banner is cosmetic, so carry on.
      }
    }
  }, [searchParams]);

  return (
    <AuthSplitLayout eyebrow="New account" title="Create your account">
      {/*
        Also completes case-worker invitations: Clerk appends __clerk_ticket to
        the invite link, and <SignUp/> picks it up from the URL automatically.
        The claimant label travels in the invitation's public_metadata and is
        applied by the backend onboarding step.
      */}
      <ClerkSignUp
        appearance={clerkAppearance}
        routing="path"
        path="/sign-up"
        signInUrl="/sign-in"
        fallbackRedirectUrl="/onboarding"
      />
    </AuthSplitLayout>
  );
}
