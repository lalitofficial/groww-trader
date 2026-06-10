"use client";

import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import type { FactorScanProgress } from "@/lib/factor-stream";

type Props = {
  progress: FactorScanProgress | null;
  onCancel?: () => void;
};

export function ScanProgress({ progress, onCancel }: Props) {
  if (!progress) return null;
  const pct = progress.total > 0 ? (progress.done / progress.total) * 100 : 0;
  const etaSeconds = progress.eta_ms !== null ? Math.max(1, Math.ceil(progress.eta_ms / 1000)) : null;
  const elapsedSeconds = Math.max(0, Math.round(progress.elapsed_ms / 1000));
  const done = progress.finished && progress.done === progress.total;

  return (
    <section className="scan-progress" aria-live="polite">
      <div className="scan-progress-head">
        {done ? (
          <CheckCircle2 size={14} className="scan-icon ok" />
        ) : (
          <Loader2 size={14} className="scan-icon scan-spin" />
        )}
        <strong>
          {done ? "Scan complete" : `Scanning ${progress.done}/${progress.total}`}
        </strong>
        <span className="muted">
          {progress.succeeded} ok · {progress.failed} failed · {elapsedSeconds}s elapsed
          {!done && etaSeconds !== null ? ` · ~${etaSeconds}s remaining` : ""}
        </span>
        {!done && onCancel ? (
          <button type="button" className="btn btn-secondary scan-cancel" onClick={onCancel}>
            <XCircle size={12} />
            Cancel
          </button>
        ) : null}
      </div>
      <div className="scan-progress-bar" role="progressbar" aria-valuenow={progress.done} aria-valuemin={0} aria-valuemax={progress.total}>
        <div className="scan-progress-fill" style={{ width: `${pct.toFixed(1)}%` }} />
      </div>
      <div className="scan-progress-flight">
        {progress.in_flight.length === 0 ? (
          <span className="muted">{done ? "All symbols processed." : "Queuing…"}</span>
        ) : (
          <>
            <span className="muted">In flight:</span>
            {progress.in_flight.slice(0, 10).map((symbol) => (
              <span key={symbol} className="scan-chip">
                {symbol}
              </span>
            ))}
            {progress.in_flight.length > 10 ? (
              <span className="muted">+{progress.in_flight.length - 10} more</span>
            ) : null}
          </>
        )}
      </div>
      {progress.errors.length > 0 ? (
        <details className="scan-errors">
          <summary>{progress.errors.length} symbol{progress.errors.length === 1 ? "" : "s"} failed</summary>
          <ul>
            {progress.errors.slice(0, 12).map((row) => (
              <li key={row.symbol}>
                <strong>{row.symbol}</strong>
                <span className="muted">{row.error}</span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}
