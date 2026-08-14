// Wraps any button/link/section that should be disabled + show a lock
// icon when the user's tier doesn't include that feature. Clicking it
// opens the upgrade modal instead of doing nothing silently.
//
// Usage:
//   <FeatureGate feature="calendar_events">
//     <Button onClick={openNewEventDialog}>+ New Event</Button>
//   </FeatureGate>
//
//   <FeatureGate feature="ai_screenshot_import" metered>
//     <Button onClick={openImportDialog}>Import Screenshot</Button>
//   </FeatureGate>

import { cloneElement } from "react";
import { LockSimpleIcon } from "@phosphor-icons/react";
import { useSubscription } from "@/hooks/useSubscription";
import { useUpgradeModal } from "@/components/UpgradeModal";

export function FeatureGate({ feature, metered = false, children, showUsage = false }) {
  const { hasFeature, getUsage } = useSubscription();
  const { show } = useUpgradeModal();

  const usage = metered ? getUsage(feature) : null;
  const allowed = metered ? !usage.exceeded : hasFeature(feature);

  if (allowed) {
    if (metered && showUsage && !usage.unlimited) {
      return (
        <div className="inline-flex items-center gap-2">
          {children}
          <span className="text-[10px] font-semibold text-muted-foreground tabular-nums">
            {usage.used}/{usage.limit}
          </span>
        </div>
      );
    }
    return children;
  }

  const message = metered
    ? `You've used all ${usage.limit} this month. Upgrade for more.`
    : `This feature isn't included on your current plan.`;

  const disabledChild = cloneElement(children, {
    onClick: () => show({ feature, message }),
    disabled: true,
    className: `${children.props.className || ""} opacity-50 cursor-not-allowed`.trim(),
  });

  return (
    <div className="inline-flex items-center gap-1.5">
      {disabledChild}
      <LockSimpleIcon size={13} weight="bold" className="text-muted-foreground" />
    </div>
  );
}

/* Small standalone lock badge for nav items / page headers where you
   don't want to disable a whole button, just flag it visually. */
export function PremiumBadge() {
  return (
    <span className="inline-flex items-center gap-1 text-[9px] font-bold tracking-widest uppercase text-primary bg-[#E8EDF7] border border-[#C5D1ED] px-1.5 py-0.5">
      <LockSimpleIcon size={9} weight="bold" />
      Pro
    </span>
  );
}