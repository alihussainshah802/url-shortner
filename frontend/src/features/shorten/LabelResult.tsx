import { Check, Copy, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { Link } from "@/api/links.ts";
import { Button } from "@/components/ui/button.tsx";

import { printedAt } from "./utils.ts";

type CopyState = "idle" | "copied" | "failed";

export function LabelResult({ link }: { link: Link }) {
  const [copyState, setCopyState] = useState<CopyState>("idle");
  const resetTimer = useRef<number | undefined>(undefined);

  const saved = link.original_url.length - link.short_url.length;

  useEffect(() => () => window.clearTimeout(resetTimer.current), []);

  async function copy() {
    try {
      // navigator.clipboard is missing on non-secure origins (plain http on a LAN
      // address) and writeText rejects when permission is denied; both land here.
      await navigator.clipboard.writeText(link.short_url);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
    window.clearTimeout(resetTimer.current);
    resetTimer.current = window.setTimeout(() => setCopyState("idle"), 2500);
  }

  return (
    // The slot hides the label until it has fed out; the wrapper clips it.
    <div className="overflow-hidden px-4 sm:px-6">
      <div className="label-feed relative text-card-foreground">
        <div className="label-edge bg-card px-5 pt-6 pb-9 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">
              Short link
            </p>
            <p
              aria-hidden
              className="label-stamp -rotate-6 rounded-sm border-2 border-accent px-2 py-0.5 font-mono text-xs font-medium tracking-widest text-accent uppercase"
            >
              Printed
            </p>
          </div>

          <a
            href={link.short_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 block font-mono text-xl font-medium break-all underline decoration-accent decoration-2 underline-offset-4 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 sm:text-2xl"
          >
            {link.short_url}
          </a>

          <p className="mt-3 truncate font-mono text-xs text-muted-foreground" title={link.original_url}>
            {link.original_url}
          </p>

          <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-dashed border-border pt-4">
            <p className="font-mono text-xs text-muted-foreground">
              {saved > 0 ? `${saved} characters shorter` : "Already short"} · {printedAt(link.created_at)}
            </p>
            <Button type="button" variant="outline" size="sm" onClick={() => void copy()}>
              {copyState === "copied" && <Check aria-hidden />}
              {copyState === "failed" && <TriangleAlert aria-hidden />}
              {copyState === "idle" && <Copy aria-hidden />}
              <span aria-live="polite">
                {copyState === "copied" && "Copied"}
                {copyState === "failed" && "Copy failed. Select the link instead"}
                {copyState === "idle" && "Copy"}
              </span>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
