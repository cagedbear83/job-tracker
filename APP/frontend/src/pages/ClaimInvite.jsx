/**
 * /claim/:ticket — branded invitation landing page.
 *
 * When a caseworker invites a claimant, Clerk sends an email with a link to
 * this page (e.g. /claim/clerk_ticket_abc123). Showing a dedicated landing
 * page gives the invitee context ("who invited you, what to expect") before
 * handing them off to the Clerk sign-up flow, which reads the ticket from
 * the __clerk_ticket query parameter automatically.
 */
import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { marketingUrl } from "@/lib/site";
import { UserPlusIcon, ShieldCheckIcon, WarningCircleIcon } from "@phosphor-icons/react";

// Minimal branded shell identical in feel to the AuthSplitLayout left panel.
function Branding() {
  return (
    <div className="hidden sm:flex flex-col justify-between bg-primary text-primary-foreground p-10 min-h-full">
      <div className="font-display font-bold text-2xl tracking-tight">
        Illinois UI Tracker
      </div>
      <div className="space-y-4">
        <blockquote className="text-lg font-medium leading-relaxed">
          "Illinois UI Tracker keeps every work-search record exactly where
          the law requires — and makes certification day painless."
        </blockquote>
      </div>
      <p className="text-xs opacity-60">
        Built for Illinois UI claimants. Not affiliated with IDES.
      </p>
    </div>
  );
}

export default function ClaimInvite() {
  const { ticket } = useParams();
  const navigate = useNavigate();
  const [valid, setValid] = useState(true); // assume valid until proven otherwise

  // A missing ticket is a broken link.
  useEffect(() => {
    if (!ticket || ticket.trim() === "") {
      setValid(false);
    }
  }, [ticket]);

  function handleAccept() {
    // Clerk's <SignUp> component reads __clerk_ticket from the URL automatically.
    navigate(`/sign-up?__clerk_ticket=${encodeURIComponent(ticket)}`);
  }

  if (!valid) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background p-6">
        <div className="max-w-md text-center space-y-4">
          <WarningCircleIcon size={48} weight="fill" className="text-destructive mx-auto" />
          <h1 className="font-display font-bold text-2xl tracking-tight">
            Invalid invitation link
          </h1>
          <p className="text-muted-foreground text-sm">
            This invitation link is missing its token. Please ask your caseworker
            to resend the invitation.
          </p>
          <Button variant="outline" onClick={() => navigate("/sign-in")}>
            Go to sign in
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen grid sm:grid-cols-2">
      <Branding />

      <div className="flex flex-col justify-center p-8 sm:p-12 bg-background">
        <div className="max-w-sm mx-auto w-full space-y-6">
          {/* Icon badge */}
          <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
            <UserPlusIcon size={24} weight="fill" className="text-primary" />
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-1">
              You've been invited
            </p>
            <h1 className="font-display font-bold text-2xl tracking-tight">
              Join Illinois UI Tracker
            </h1>
          </div>

          <p className="text-sm text-muted-foreground leading-relaxed">
            Your caseworker has set up an Illinois UI Tracker account for you.
            Click below to create your account — your caseworker's details
            are already attached so you can get started immediately.
          </p>

          <ul className="space-y-2 text-sm text-muted-foreground">
            <li className="flex items-start gap-2">
              <ShieldCheckIcon size={16} weight="fill" className="text-primary mt-0.5 shrink-0" />
              Track all 4 weekly work-search contacts in one place
            </li>
            <li className="flex items-start gap-2">
              <ShieldCheckIcon size={16} weight="fill" className="text-primary mt-0.5 shrink-0" />
              Automatic certification-day reminders
            </li>
            <li className="flex items-start gap-2">
              <ShieldCheckIcon size={16} weight="fill" className="text-primary mt-0.5 shrink-0" />
              Export records for IDES at any time
            </li>
          </ul>

          <Button
            className="w-full rounded-none bg-primary hover:bg-primary/90"
            onClick={handleAccept}
          >
            Accept invitation &amp; create account
          </Button>

          <p className="text-xs text-muted-foreground text-center">
            Already have an account?{" "}
            <a href="/sign-in" className="underline underline-offset-2 hover:text-foreground">
              Sign in instead
            </a>
          </p>

          <p className="text-xs text-muted-foreground/60 text-center">
            By creating an account you agree to our{" "}
            <a
              href={marketingUrl("/terms")}
              target="_blank"
              rel="noreferrer"
              className="underline underline-offset-2"
            >
              Terms
            </a>{" "}
            and{" "}
            <a
              href={marketingUrl("/privacy")}
              target="_blank"
              rel="noreferrer"
              className="underline underline-offset-2"
            >
              Privacy Policy
            </a>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
