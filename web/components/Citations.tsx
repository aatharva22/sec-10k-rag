"use client";

import type { Citation } from "@/lib/types";
import CitationCard from "./CitationCard";

interface Props {
  citations: Citation[];
  showDetails?: boolean;
}

export default function Citations({ citations, showDetails }: Props) {
  if (citations.length === 0) return null;
  return (
    <div className="mt-3">
      <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted">
        Sources &middot; {citations.length}
      </div>
      <div className="scroll-strip -mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
        {citations.map((c) => (
          <CitationCard key={c.chunk_id} citation={c} showDetails={showDetails} />
        ))}
      </div>
    </div>
  );
}
