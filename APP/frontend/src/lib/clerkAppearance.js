/**
 * Themes Clerk's prebuilt components with the shared brand tokens.
 *
 * The tokens live in src/brand-tokens.css as raw HSL triples (canonical copy
 * in APP/brand/tokens.css, byte-identical on illinoisjobtracker.com). Clerk's
 * appearance API wants real CSS colors, so each one is wrapped in hsl(var(…))
 * — which means Clerk follows dark mode automatically, with no second theme
 * to maintain and no chance of the auth screens drifting from the rest of the
 * product the way a hardcoded palette would.
 */
const t = (name) => `hsl(var(--${name}))`;

export const clerkAppearance = {
  variables: {
    colorPrimary: t("primary"),
    colorBackground: t("background"),
    colorText: t("foreground"),
    colorTextSecondary: t("muted-foreground"),
    colorInputBackground: t("background"),
    colorInputText: t("foreground"),
    colorDanger: t("destructive"),
    colorSuccess: t("success"),
    colorWarning: t("warning"),
    colorNeutral: t("foreground"),
    // Sharp corners — the Swiss/flat language the rest of the app uses.
    borderRadius: "0.125rem",
    fontFamily: "var(--font-body)",
    fontFamilyButtons: "var(--font-body)",
    fontSize: "0.875rem",
  },
  elements: {
    // Clerk's card would otherwise sit inside our own heading block with its
    // own border, shadow and padding — a card in a card.
    rootBox: "w-full",
    cardBox: "w-full shadow-none border-0",
    card: "bg-transparent shadow-none border-0 p-0 gap-4",
    header: "hidden", // AuthSplitLayout already renders the title
    footer: "bg-transparent",
    footerAction: "justify-start",

    formButtonPrimary:
      "bg-primary text-primary-foreground hover:bg-primary-hover normal-case font-semibold tracking-normal shadow-none",
    socialButtonsBlockButton:
      "border border-border hover:bg-secondary text-foreground shadow-none",
    formFieldInput:
      "border border-input bg-background text-foreground focus:ring-2 focus:ring-ring shadow-none",
    formFieldLabel: "text-foreground font-medium",
    dividerLine: "bg-border",
    dividerText: "text-muted-foreground",
    identityPreviewEditButton: "text-primary",
    footerActionLink: "text-primary font-semibold hover:text-primary-hover",
    formResendCodeLink: "text-primary font-semibold",
    otpCodeFieldInput: "border border-input bg-background text-foreground",
  },
};
