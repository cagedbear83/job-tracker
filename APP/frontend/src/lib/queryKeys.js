/**
 * Centralized TanStack Query key factory.
 *
 * Rules:
 *  - Every key is an array so TanStack can do prefix-based invalidation.
 *  - Broader keys are prefixes of narrower keys, so invalidating
 *    queryKeys.weeks.all() also busts .detail(id) caches automatically.
 */
export const queryKeys = {
  dashboard: {
    stats: ()       => ["dashboard", "stats"],
    trend: (range)  => ["dashboard", "trend", range],
  },
  weeks: {
    all:    ()   => ["weeks"],
    detail: (id) => ["weeks", String(id)],
  },
  contacts: {
    all:    ()       => ["contacts"],
    byWeek: (weekId) => ["contacts", "byWeek", String(weekId)],
  },
  profile: {
    me: () => ["profile"],
  },
};
