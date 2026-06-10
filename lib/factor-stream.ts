import { getFactorSnapshot } from "@/lib/api";
import type { FactorSnapshot, Timeframe } from "@/lib/types";

export type FactorScanProgress = {
  done: number;
  total: number;
  succeeded: number;
  failed: number;
  in_flight: string[];
  latest?: FactorSnapshot;
  errors: Array<{ symbol: string; error: string }>;
  elapsed_ms: number;
  eta_ms: number | null;
  finished: boolean;
};

export type FactorScanHandle = {
  promise: Promise<FactorSnapshot[]>;
  cancel: () => void;
};

/**
 * Runs the factor pipeline one symbol at a time with a JS-side concurrency
 * limiter so the UI can show live progress + per-row results as they arrive.
 *
 * The backend `/api/factors/batch` returns only when every symbol is done,
 * which feels frozen for a 100-symbol scan. Calling `/api/factors/{symbol}`
 * N times in parallel lets us paint rows progressively, surface in-flight
 * symbols, and cancel cleanly.
 */
export function runFactorScan(
  symbols: string[],
  options: {
    timeframe?: Timeframe;
    refresh?: boolean;
    concurrency?: number;
    onProgress: (progress: FactorScanProgress) => void;
    onRow: (row: FactorSnapshot) => void;
  },
): FactorScanHandle {
  const { timeframe = "daily", refresh = false, concurrency = 6, onProgress, onRow } = options;
  const total = symbols.length;
  const inFlight = new Set<string>();
  const completed: FactorSnapshot[] = [];
  const errors: Array<{ symbol: string; error: string }> = [];
  const started = typeof performance !== "undefined" ? performance.now() : Date.now();

  let cursor = 0;
  let cancelled = false;

  function nowMs() {
    return (typeof performance !== "undefined" ? performance.now() : Date.now()) - started;
  }

  function publish(latest?: FactorSnapshot, finished = false) {
    const elapsed = nowMs();
    const completedCount = completed.length + errors.length;
    const remaining = Math.max(0, total - completedCount);
    const eta = completedCount > 0 && remaining > 0 ? (elapsed / completedCount) * remaining : null;
    onProgress({
      done: completedCount,
      total,
      succeeded: completed.length,
      failed: errors.length,
      in_flight: Array.from(inFlight),
      latest,
      errors,
      elapsed_ms: elapsed,
      eta_ms: eta,
      finished,
    });
  }

  async function worker() {
    while (!cancelled) {
      const idx = cursor++;
      if (idx >= total) break;
      const symbol = symbols[idx];
      inFlight.add(symbol);
      publish();
      try {
        const row = await getFactorSnapshot(symbol, timeframe, refresh);
        completed.push(row);
        onRow(row);
        publish(row);
      } catch (exc) {
        errors.push({ symbol, error: exc instanceof Error ? exc.message : String(exc) });
        publish();
      } finally {
        inFlight.delete(symbol);
      }
    }
  }

  const lanes = Math.max(1, Math.min(concurrency, total));
  const workers = Array.from({ length: lanes }, () => worker());

  const promise = Promise.all(workers).then(() => {
    publish(undefined, true);
    return completed;
  });

  return {
    promise,
    cancel: () => {
      cancelled = true;
    },
  };
}
