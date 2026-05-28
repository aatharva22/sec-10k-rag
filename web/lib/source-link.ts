/**
 * Build a citation link that deep-jumps to the cited text on the source
 * EDGAR page using a browser Text Fragment (`#:~:text=...`).
 *
 * Modern Chromium, Safari 16.1+, and Firefox (behind a flag) scroll to and
 * highlight the matching text. Browsers that don't support the syntax just
 * land on the document — graceful degradation.
 *
 * For quotes longer than ~8 words, we anchor on the first and last few
 * words (`textStart,textEnd`) rather than the full string. This is more
 * resilient: any single-char mismatch in the middle (smart-quote vs
 * straight quote, soft hyphen, etc.) won't break the match.
 */
export function buildSourceLink(sourceUrl: string, quote: string): string {
  const cleaned = quote
    .trim()
    // strip surrounding quotes (curly or straight) — quotes in the DB are
    // verbatim but the LLM occasionally wraps them
    .replace(/^["'“‘«]+|["'”’»]+$/g, "")
    // strip a leading bracketed section label like "[Item 1A. Risk Factors] "
    .replace(/^\[[^\]]+\]\s*/, "")
    .trim();

  if (!cleaned) return sourceUrl;

  // Drop any existing hash on the URL so we don't clobber ourselves.
  const base = sourceUrl.split("#")[0];
  const words = cleaned.split(/\s+/);

  let fragment: string;
  if (words.length <= 8) {
    fragment = encodeURIComponent(cleaned);
  } else {
    const startWords = words.slice(0, 5).join(" ");
    const endWords = words.slice(-5).join(" ");
    fragment = `${encodeURIComponent(startWords)},${encodeURIComponent(endWords)}`;
  }

  return `${base}#:~:text=${fragment}`;
}
