/**
 * Shared date utilities for Illinois UI compliance.
 * Mandates a strict Sunday-to-Saturday tracking window.
 */

/**
 * Returns the YYYY-MM-DD string for the Sunday of the provided date's week.
 */
export function getSunday(d = new Date()) {
  const date = new Date(d);
  const day = date.getDay();
  date.setDate(date.getDate() - day);
  return date.toISOString().slice(0, 10);
}

/**
 * Returns the YYYY-MM-DD string for the Saturday following a given Sunday.
 */
export function getSaturday(sundayStr) {
  const d = new Date(sundayStr + "T00:00:00");
  d.setDate(d.getDate() + 6);
  return d.toISOString().slice(0, 10);
}

/**
 * Standardizes date formatting to ISO (YYYY-MM-DD) for backend compatibility.
 */
export function formatISODate(date) {
  return new Date(date).toISOString().slice(0, 10);
}