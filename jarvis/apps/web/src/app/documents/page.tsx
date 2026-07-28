"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Download, FileText, Trash2 } from "lucide-react";
import {
  API_BASE,
  api,
  streamDocument,
  type DocumentDetail,
  type DocumentSummary,
} from "@/lib/api";
import { useMode } from "@/lib/mode";
import {
  Card,
  Chip,
  EmptyState,
  ErrorState,
  PageHeader,
  SectionLabel,
  Skeleton,
} from "@/components/ui";

/**
 * Documents Jarvis has written.
 *
 * Composition streams the outline first and then fills it in, and this page
 * shows that honestly: the headings appear before any prose, so the moment to
 * say "no, not that shape" is before the writing has been paid for.
 */

const KINDS = ["report", "brief", "proposal", "memo", "spec", "summary"];

export default function DocumentsPage() {
  const { mode } = useMode();
  const [documents, setDocuments] = useState<DocumentSummary[] | null>(null);
  const [error, setError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const [request, setRequest] = useState("");
  const [kind, setKind] = useState("report");
  const [busy, setBusy] = useState(false);
  const [outline, setOutline] = useState<string[]>([]);
  const [writing, setWriting] = useState("");
  const [open, setOpen] = useState<DocumentDetail | null>(null);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .generatedDocuments()
      .then((next) => {
        if (cancelled) return;
        setDocuments(next);
        setError(false);
      })
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const reload = useCallback(() => setReloadKey((key) => key + 1), []);

  const compose = useCallback(async () => {
    const text = request.trim();
    if (!text || busy) return;

    setBusy(true);
    setOutline([]);
    setWriting("");
    setOpen(null);
    const controller = new AbortController();
    abort.current = controller;

    try {
      for await (const event of streamDocument(text, {
        kind,
        mode,
        signal: controller.signal,
      })) {
        if (event.type === "outline")
          setOutline(event.sections.map((s) => s.heading));
        else if (event.type === "section") setWriting(event.heading);
        else if (event.type === "done") {
          setRequest("");
          setWriting("");
          reload();
          api
            .document(event.id)
            .then(setOpen)
            .catch(() => {});
        } else if (event.type === "error")
          setWriting(`Failed: ${event.message}`);
      }
    } catch {
      /* aborted, or the kernel is down — the list state already says so */
    } finally {
      setBusy(false);
      abort.current = null;
    }
  }, [request, kind, mode, busy, reload]);

  const remove = useCallback(
    async (id: string) => {
      await api.deleteDocument(id);
      if (open?.id === id) setOpen(null);
      reload();
    },
    [open, reload],
  );

  return (
    <div className="mx-auto max-w-[900px] px-10 py-12">
      <PageHeader
        title="Documents"
        subtitle="Things Jarvis wrote, planned as an outline and sourced from what it knows."
      />

      <Card className="mb-8">
        <div className="flex flex-col gap-3">
          <textarea
            value={request}
            onChange={(event) => setRequest(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && (event.metaKey || event.ctrlKey))
                compose();
            }}
            rows={2}
            placeholder="What should it cover? e.g. “Q3 review of the supplement line, with the margin risk”"
            data-testid="document-request"
            className="w-full resize-none rounded-control border border-hairline bg-surface px-3 py-2.5 text-[14px] text-ink outline-none transition-colors placeholder:text-ink-3 focus:border-accent/50"
          />
          <div className="flex items-center gap-2">
            <select
              value={kind}
              onChange={(event) => setKind(event.target.value)}
              aria-label="Document kind"
              className="rounded-control border border-hairline bg-surface px-2.5 py-1.5 text-[13px] text-ink-2 outline-none"
            >
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
            <span className="text-[12.5px] text-ink-3">{mode} mode</span>
            <button
              onClick={compose}
              disabled={busy || !request.trim()}
              data-testid="compose"
              className="ml-auto rounded-control bg-accent px-3.5 py-1.5 text-[13px] font-medium text-canvas transition-opacity disabled:opacity-40"
            >
              {busy ? "Writing…" : "Write it"}
            </button>
          </div>
        </div>
      </Card>

      {outline.length > 0 && (
        <>
          <SectionLabel>Outline</SectionLabel>
          <Card className="mb-8">
            <ol className="flex flex-col gap-1.5" data-testid="outline">
              {outline.map((heading) => (
                <li
                  key={heading}
                  className="flex items-center gap-2 text-[13.5px]"
                >
                  <span
                    className={
                      heading === writing ? "text-accent" : "text-ink-2"
                    }
                  >
                    {heading}
                  </span>
                  {heading === writing && (
                    <span className="text-[11.5px] uppercase tracking-wider text-accent">
                      writing
                    </span>
                  )}
                </li>
              ))}
            </ol>
          </Card>
        </>
      )}

      {open && (
        <>
          <SectionLabel>{open.title}</SectionLabel>
          <Card className="mb-8">
            <div data-testid="document-body">
              {open.sections.map((section) => (
                <div key={section.id} className="mb-6 last:mb-0">
                  <h3 className="mb-1.5 text-[15px] font-medium text-ink">
                    {section.heading}
                  </h3>
                  <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-ink-2">
                    {section.body}
                  </p>
                </div>
              ))}
            </div>
            {open.references.length > 0 && (
              <div className="mt-6 border-t border-hairline pt-4">
                <p className="mb-2 text-[12px] uppercase tracking-wider text-ink-3">
                  Sources
                </p>
                <ol className="flex flex-col gap-1 text-[13px] text-ink-3">
                  {open.references.map((reference, index) => (
                    <li key={`${reference.reference}-${index}`}>
                      {index + 1}. {reference.reference}
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </Card>
        </>
      )}

      <SectionLabel>Library</SectionLabel>
      {error ? (
        <ErrorState message="Could not load documents." onRetry={reload} />
      ) : documents === null ? (
        <Skeleton className="h-[120px] w-full" />
      ) : documents.length === 0 ? (
        <EmptyState
          title="Nothing written yet."
          action="Describe a document above."
        />
      ) : (
        <div className="flex flex-col gap-1.5">
          {documents.map((document) => (
            <motion.div
              key={document.id}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <Card>
                <div className="flex items-start gap-2.5">
                  <FileText size={15} className="mt-0.5 shrink-0 text-ink-3" />
                  <button
                    onClick={() =>
                      api
                        .document(document.id)
                        .then(setOpen)
                        .catch(() => {})
                    }
                    className="min-w-0 flex-1 text-left"
                  >
                    <p className="truncate text-[13.5px] text-ink">
                      {document.title}
                    </p>
                    <p className="mt-0.5 text-[12.5px] text-ink-3">
                      {document.kind} · {document.sections} sections ·{" "}
                      {document.words} words
                      {document.citations > 0 &&
                        ` · ${document.citations} sources`}
                    </p>
                  </button>
                  {document.mode !== "personal" && (
                    <Chip tone="neutral">{document.mode}</Chip>
                  )}
                  <a
                    href={`${API_BASE}/v1/documents/${document.id}/export?format=md`}
                    aria-label={`Export ${document.title}`}
                    className="text-ink-3 transition-colors hover:text-ink"
                  >
                    <Download size={15} />
                  </a>
                  <button
                    onClick={() => remove(document.id)}
                    aria-label={`Delete ${document.title}`}
                    className="text-ink-3 transition-colors hover:text-danger"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
