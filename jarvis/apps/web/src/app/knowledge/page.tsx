"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { FileText, Link2, Trash2 } from "lucide-react";
import { api, type CitationHit, type KnowledgeDoc } from "@/lib/api";
import { Chip, ErrorState, PageHeader, SectionLabel, Skeleton } from "@/components/ui";

/**
 * Knowledge.
 *
 * The design bet: retrieval is only trustworthy if you can see *where* an
 * answer came from. So search results lead with the citation — document and
 * locator — and the passage is secondary. A snippet without a reference is
 * exactly the thing this page exists to stop.
 */
export default function KnowledgePage() {
  const [documents, setDocuments] = useState<KnowledgeDoc[] | null>(null);
  const [hits, setHits] = useState<CitationHit[] | null>(null);
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .documents()
      .then((found) => {
        if (cancelled) return;
        setDocuments(found);
        setError(false);
      })
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  // Debounced search, so typing does not issue a request per keystroke.
  useEffect(() => {
    const text = query.trim();
    let cancelled = false;
    const timer = setTimeout(() => {
      if (text.length < 3) {
        setHits(null);
        return;
      }
      api
        .searchKnowledge(text)
        .then((found) => !cancelled && setHits(found))
        .catch(() => !cancelled && setHits([]));
    }, 220);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query]);

  const ingest = async () => {
    const value = source.trim();
    if (!value) return;
    setBusy(true);
    setNotice(null);
    try {
      // A URL is fetched; anything else is treated as pasted text. Paths are
      // resolved server-side inside the workspace, never here.
      const body = value.startsWith("http")
        ? { url: value }
        : { text: value, title: value.slice(0, 60) };
      const result = await api.ingest(body);

      const skipped = Object.values(result.skipped);
      setNotice(
        result.ingested.length
          ? `Ingested ${result.ingested[0].title} — ${result.chunks} chunks`
          : result.unchanged.length
            ? `Already known: ${result.unchanged[0]}`
            : (skipped[0] ?? "Nothing readable in that source"),
      );
      setSource("");
      setReloadKey((key) => key + 1);
    } catch {
      setNotice("Could not ingest that source");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    await api.forgetDocument(id);
    setReloadKey((key) => key + 1);
  };

  return (
    <div className="mx-auto max-w-[900px] px-10 py-12">
      <PageHeader
        title="Knowledge"
        subtitle="What Jarvis has read. Every answer drawn from here cites the page it came from."
      />

      <div className="mb-8 flex gap-2">
        <input
          value={source}
          onChange={(event) => setSource(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && void ingest()}
          placeholder="Paste a URL, or text to remember…"
          className="flex-1 rounded-control border border-hairline bg-surface px-3.5 py-2.5 text-[13.5px] outline-none transition-colors placeholder:text-ink-3 focus:border-accent/40"
        />
        <button
          onClick={() => void ingest()}
          disabled={busy || !source.trim()}
          className="rounded-control bg-accent/15 px-4 text-[13px] text-accent transition-colors hover:bg-accent/25 disabled:opacity-30"
        >
          {busy ? "Reading…" : "Ingest"}
        </button>
      </div>

      {notice && <p className="mb-6 text-[12.5px] text-ink-3">{notice}</p>}

      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Ask across everything Jarvis has read…"
        className="mb-6 w-full rounded-control border border-hairline bg-surface px-3.5 py-2.5 text-[13.5px] outline-none transition-colors placeholder:text-ink-3 focus:border-accent/40"
      />

      {hits !== null && (
        <section className="mb-10">
          <SectionLabel>{hits.length ? "Passages" : "No passages matched"}</SectionLabel>
          <div className="flex flex-col gap-2">
            {hits.map((hit, index) => (
              <motion.div
                key={`${hit.document_id}-${index}`}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.03 }}
                className="card px-4 py-3.5"
              >
                {/* Citation first: the passage means nothing without it. */}
                <div className="mb-1.5 flex items-baseline gap-2">
                  <Chip tone="accent">{hit.reference}</Chip>
                  <span className="ml-auto font-mono text-[10px] text-ink-3">
                    lex {hit.signals.lexical.toFixed(2)} · sem {hit.signals.semantic.toFixed(2)}
                  </span>
                </div>
                <p className="text-[13px] leading-relaxed text-ink-2">{hit.snippet}</p>
              </motion.div>
            ))}
          </div>
        </section>
      )}

      <SectionLabel>Documents</SectionLabel>
      {error ? (
        <ErrorState
          message="Could not load documents."
          onRetry={() => setReloadKey((key) => key + 1)}
        />
      ) : documents === null ? (
        <div className="flex flex-col gap-2">
          {[0, 1, 2].map((index) => (
            <Skeleton key={index} className="h-[54px] w-full" />
          ))}
        </div>
      ) : documents.length === 0 ? (
        <div className="card px-5 py-10 text-center text-[13px] text-ink-3">
          Nothing ingested yet. Paste a URL or some text above.
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
          {documents.map((document, index) => (
            <motion.div
              key={document.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(index * 0.02, 0.2) }}
              className="card group flex items-center gap-3 px-4 py-3"
            >
              {document.source.startsWith("http") ? (
                <Link2 size={14} className="shrink-0 text-ink-3" />
              ) : (
                <FileText size={14} className="shrink-0 text-ink-3" />
              )}
              <span className="flex-1 truncate text-[13.5px]">{document.title}</span>
              <Chip>{document.kind}</Chip>
              <span className="w-20 shrink-0 text-right font-mono text-[10.5px] text-ink-3">
                {document.chunk_count} chunks
              </span>
              <button
                onClick={() => void remove(document.id)}
                aria-label={`Forget ${document.title}`}
                className="text-ink-3 opacity-0 transition-opacity hover:text-danger group-hover:opacity-100"
              >
                <Trash2 size={13} />
              </button>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
