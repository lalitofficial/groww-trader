"use client";

import { ArrowRight, X } from "lucide-react";
import { useState } from "react";
import { setSessionPicks } from "@/lib/api";
import { useRouter } from "next/navigation";

type Pick = { symbol: string; direction: "long" | "short" };

export function PicksTray({ picks, setPicks }: { picks: Pick[]; setPicks: (next: Pick[]) => void }) {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function remove(symbol: string) {
    setPicks(picks.filter((pick) => pick.symbol !== symbol));
  }

  async function commit() {
    if (!picks.length) return;
    setSaving(true);
    setError("");
    try {
      await setSessionPicks(picks.map((pick) => ({ symbol: pick.symbol, direction: pick.direction })));
      router.push("/live-desk");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <aside className="picks-tray">
      <header>
        <strong>Picks tray</strong>
        <span className="muted">{picks.length} symbols ready</span>
      </header>
      {error ? <div className="context-badge warning">{error}</div> : null}
      <div className="picks-chips">
        {picks.map((pick) => (
          <span key={pick.symbol} className={`pick-chip pick-${pick.direction}`}>
            <strong>{pick.symbol}</strong>
            <span>{pick.direction}</span>
            <button type="button" className="btn-icon" onClick={() => remove(pick.symbol)}>
              <X size={11} />
            </button>
          </span>
        ))}
        {picks.length === 0 ? <span className="muted">Promote shortlist entries to fill this tray.</span> : null}
      </div>
      <button type="button" className="btn btn-primary" onClick={commit} disabled={saving || picks.length === 0}>
        {saving ? "Saving…" : "Commit picks → Live Desk"}
        <ArrowRight size={13} />
      </button>
    </aside>
  );
}
