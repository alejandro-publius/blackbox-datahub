"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Radar, X } from "lucide-react";
import { Button } from "@/components/ui/button";

export const DEFAULT_REPORT_TEXT =
  "Revenue just jumped roughly 100x on the executive dashboard. Is this real?";

/**
 * Intake dialog: an on-call engineer files a report, the agent takes it from
 * there. Prefilled with the demo report; POSTs via the onSubmit callback.
 */
export function IncidentDialog({
  open,
  onClose,
  onSubmit,
  submitting,
  error,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (reportText: string) => void;
  submitting?: boolean;
  error?: string | null;
}) {
  const [text, setText] = useState(DEFAULT_REPORT_TEXT);
  const [wasOpen, setWasOpen] = useState(open);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Render-time state adjustment: re-prefill whenever the dialog (re)opens.
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) setText(DEFAULT_REPORT_TEXT);
  }

  useEffect(() => {
    if (!open) return;
    // focus after the enter animation starts
    const t = setTimeout(() => textareaRef.current?.focus(), 60);
    return () => clearTimeout(t);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, submitting, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm"
          onClick={() => !submitting && onClose()}
        >
          <motion.div
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="w-full max-w-lg rounded-xl border border-zinc-700 bg-zinc-900 p-5 shadow-2xl shadow-black/60"
            role="dialog"
            aria-modal="true"
            aria-label="Report an incident"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 text-zinc-100">
                  <Radar className="size-4 text-sky-400" />
                  <h2 className="text-sm font-bold tracking-[0.14em]">
                    REPORT INCIDENT
                  </h2>
                </div>
                <p className="mt-1 text-xs leading-relaxed text-zinc-400">
                  Describe what you are seeing. The agent will traverse
                  lineage, test hypotheses against the warehouse, and confirm a
                  root cause with evidence.
                </p>
              </div>
              <button
                type="button"
                onClick={onClose}
                disabled={submitting}
                className="rounded-md p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-200"
                aria-label="Close"
              >
                <X className="size-4" />
              </button>
            </div>

            <textarea
              ref={textareaRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={4}
              disabled={submitting}
              className="mt-4 w-full resize-none rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2.5 font-mono text-[13px] leading-relaxed text-zinc-100 placeholder:text-zinc-600 focus:border-sky-400/60 focus:ring-1 focus:ring-sky-400/40 focus:outline-none"
              placeholder="What looks wrong?"
            />

            {error && (
              <p className="mt-2 rounded-md border border-red-400/40 bg-red-400/10 px-3 py-2 font-mono text-[11px] text-red-400">
                {error}
              </p>
            )}

            <div className="mt-4 flex items-center justify-end gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={onClose}
                disabled={submitting}
                className="text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={() => onSubmit(text.trim())}
                disabled={submitting || text.trim().length === 0}
                className="bg-sky-500 text-white hover:bg-sky-600"
              >
                {submitting ? (
                  <Loader2 data-icon="inline-start" className="animate-spin" />
                ) : (
                  <Radar data-icon="inline-start" />
                )}
                {submitting ? "Dispatching agent…" : "Start Investigation"}
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
