import { SignIn as ClerkSignIn } from "@clerk/clerk-react";
import AuthSplitLayout from "@/components/AuthSplitLayout";
import { clerkAppearance } from "@/lib/clerkAppearance";

export default function SignIn() {
  return (
    <AuthSplitLayout eyebrow="Authentication" title="Sign in">
      <ClerkSignIn
        appearance={clerkAppearance}
        routing="path"
        path="/sign-in"
        signUpUrl="/sign-up"
        // Onboarding decides where to actually land — App.jsx redirects to
        // /onboarding when the account has no claimant profile yet.
        fallbackRedirectUrl="/dashboard"
      />
    </AuthSplitLayout>
  );
}
