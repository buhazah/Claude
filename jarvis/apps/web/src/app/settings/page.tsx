"use client";

import { useCallback, useEffect, useState } from "react";
import { KeyRound, Trash2 } from "lucide-react";
import { api, type BudgetStatus, type SecretInfo } from "@/lib/api";
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
 * Secrets and spending.
 *
 * There is no view of a secret here because there is no endpoint that returns
 * one — the list carries a name, a length and a few characters, nothing else.
 * Agents reference a secret by name; the value is substituted inside the tool
 * registry and scrubbed from anything on its way back out.
 */
export default function SettingsPage() {
  const [vault, setVault] = useState<{ locked: boolean; secrets: SecretInfo[] } | null>(null);
  const [budget, setBudget] = useState<BudgetStatus | null>(null);
  const [error, setError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  const [problem, setProblem] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.secrets(), api.budget()])
      .then(([secrets, spend]) => {
        if (cancelled) return;
        setVault(secrets);
        setBudget(spend);
        setError(false);
      })
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const reload = useCallback(() => setReloadKey((key) => key + 1), []);

  const save = useCallback(async () => {
    if (!name.trim() || !value.trim()) return;
    try {
      await api.putSecret(name.trim(), value);
      setName("");
      setValue("");
      setProblem("");
      reload();
    } catch {
      setProblem("Could not store that — is a vault key configured?");
    }
  }, [name, value, reload]);

  if (error) {
    return (
      <div className="mx-auto max-w-[820px] px-10 py-12">
        <ErrorState message="Could not load settings." onRetry={reload} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[820px] px-10 py-12">
      <PageHeader
        title="Settings"
        subtitle="Secrets Jarvis can use without ever seeing, and the ceilings on what it can spend."
      />

      <SectionLabel>Spending</SectionLabel>
      {budget === null ? (
        <Skeleton className="h-[90px] w-full" />
      ) : (
        <Card className="mb-8">
          {!budget.enforced ? (
            <p className="text-[13.5px] text-ink-3" data-testid="budget-off">
              No ceilings set. Jarvis will spend whatever a request costs — set{" "}
              <code className="text-ink-2">JARVIS_DAILY_BUDGET_HARD_USD</code> to change that.
            </p>
          ) : (
            <div className="flex flex-col gap-2.5" data-testid="budgets">
              {budget.budgets.map((line) => (
                <div key={line.period} className="flex items-center gap-2 text-[13.5px]">
                  <span className="w-16 text-ink-3">{line.period}</span>
                  <span className="text-ink">${line.spent_usd.toFixed(4)}</span>
                  {line.soft_usd > 0 && <Chip tone="warning">asks at ${line.soft_usd}</Chip>}
                  {line.hard_usd > 0 && <Chip tone="danger">stops at ${line.hard_usd}</Chip>}
                </div>
              ))}
            </div>
          )}
          <p className="mt-3 text-[12.5px] leading-relaxed text-ink-3">
            Checked before each call, against a deliberately conservative estimate. The soft
            ceiling asks you; the hard ceiling refuses without asking.
          </p>
        </Card>
      )}

      <SectionLabel>Secrets</SectionLabel>
      {vault === null ? (
        <Skeleton className="h-[140px] w-full" />
      ) : (
        <>
          <Card className="mb-4">
            {vault.locked ? (
              <p className="text-[13.5px] text-warning" data-testid="vault-locked">
                The vault is locked — no key is configured, so nothing can be stored. Generate one
                with <code className="text-ink-2">python -m jarvis.security.keygen</code> and set{" "}
                <code className="text-ink-2">JARVIS_VAULT_KEY</code>.
              </p>
            ) : (
              <div className="flex flex-col gap-2.5">
                <div className="flex gap-2">
                  <input
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    placeholder="name, e.g. stripe"
                    data-testid="secret-name"
                    className="w-40 rounded-control border border-hairline bg-surface px-2.5 py-1.5 text-[13px] text-ink outline-none placeholder:text-ink-3 focus:border-accent/50"
                  />
                  <input
                    value={value}
                    onChange={(event) => setValue(event.target.value)}
                    type="password"
                    placeholder="value"
                    data-testid="secret-value"
                    className="flex-1 rounded-control border border-hairline bg-surface px-2.5 py-1.5 text-[13px] text-ink outline-none placeholder:text-ink-3 focus:border-accent/50"
                  />
                  <button
                    onClick={save}
                    data-testid="secret-save"
                    className="rounded-control bg-accent px-3 py-1.5 text-[13px] font-medium text-canvas"
                  >
                    Store
                  </button>
                </div>
                <p className="text-[12.5px] text-ink-3">
                  Reference it in a tool as <code className="text-ink-2">{"${vault:name}"}</code>.
                  Jarvis substitutes the value at call time — the model never holds it, and it is
                  scrubbed from logs, events and the audit trail.
                </p>
                {problem && <p className="text-[12.5px] text-danger">{problem}</p>}
              </div>
            )}
          </Card>

          {vault.secrets.length === 0 ? (
            <EmptyState title="No secrets stored." />
          ) : (
            <div className="flex flex-col gap-1.5" data-testid="secret-list">
              {vault.secrets.map((secret) => (
                <Card key={secret.name}>
                  <div className="flex items-center gap-2.5">
                    <KeyRound size={15} className="shrink-0 text-ink-3" />
                    <span className="text-[13.5px] text-ink">{secret.name}</span>
                    <span className="font-mono text-[12.5px] text-ink-3">{secret.hint}</span>
                    <span className="text-[12.5px] text-ink-3">{secret.length} chars</span>
                    <button
                      onClick={() => api.deleteSecret(secret.name).then(reload)}
                      aria-label={`Delete ${secret.name}`}
                      className="ml-auto text-ink-3 transition-colors hover:text-danger"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
