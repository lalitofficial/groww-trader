"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getPublicQuote } from "@/lib/api";

export type LivePriceState = {
  price: number | null;
  provider: string | null;
  freshness: string | null;
  driftFromEntryPct: number | null;
  distanceToStopPct: number | null;
  loading: boolean;
  error: string | null;
};

export function useLivePrice(
  symbol: string,
  anchors: { entry?: number | null; stop?: number | null; fallbackPrice?: number | null } = {},
): LivePriceState {
  const [price, setPrice] = useState<number | null>(numberOrNull(anchors.fallbackPrice));
  const [provider, setProvider] = useState<string | null>(null);
  const [freshness, setFreshness] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const quote = await getPublicQuote(symbol);
      const nextPrice = numberOrNull(quote.ltp ?? quote.price ?? quote.last_price ?? quote.close);
      setPrice(nextPrice ?? numberOrNull(anchors.fallbackPrice));
      setProvider(typeof quote.provider === "string" ? quote.provider : null);
      setFreshness(typeof quote.freshness === "string" ? quote.freshness : typeof quote.timestamp === "string" ? quote.timestamp : null);
      setError(null);
    } catch (exc) {
      setPrice((current) => current ?? numberOrNull(anchors.fallbackPrice));
      setError(exc instanceof Error ? exc.message : "Live quote unavailable");
    } finally {
      setLoading(false);
    }
  }, [anchors.fallbackPrice, symbol]);

  useEffect(() => {
    void load();
    const id = window.setInterval(load, 30_000);
    return () => window.clearInterval(id);
  }, [load]);

  return useMemo(() => {
    const entry = numberOrNull(anchors.entry);
    const stop = numberOrNull(anchors.stop);
    return {
      price,
      provider,
      freshness,
      driftFromEntryPct: price !== null && entry ? ((price - entry) / entry) * 100 : null,
      distanceToStopPct: price !== null && stop ? ((price - stop) / price) * 100 : null,
      loading,
      error,
    };
  }, [anchors.entry, anchors.stop, error, freshness, loading, price, provider]);
}

function numberOrNull(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
