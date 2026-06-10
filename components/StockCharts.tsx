"use client";

import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import { DockviewReact, type DockviewApi, type DockviewReadyEvent, type IDockviewPanelProps, themeAbyss } from "dockview";
import { Activity, BarChart3 } from "lucide-react";
import type { ReactNode, RefObject } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Candle, ChartMarker, ChartOverlays } from "@/lib/types";

type Level = {
  level: number;
  type: "support" | "resistance";
  strength: number;
  distance_pct: number;
  touches: number;
  last_touch_at?: number | null;
  recency_score?: number | null;
  volume_score?: number | null;
  breakout_state?: string | null;
};

type ChartPanelId = "price_action" | "volume" | "momentum" | "volatility" | "levels";
type Timeframe = "daily" | "hourly" | "intraday";
type Mode = "swing" | "quant";

type ToggleState = {
  ma: boolean;
  vwap: boolean;
  supertrend: boolean;
  bbkc: boolean;
  levels: boolean;
  breakouts: boolean;
  divergences: boolean;
  volumeSpikes: boolean;
};

const DEFAULT_TOGGLES: ToggleState = {
  ma: true,
  vwap: true,
  supertrend: true,
  bbkc: true,
  levels: true,
  breakouts: true,
  divergences: true,
  volumeSpikes: true,
};

export function StockCharts({
  daily,
  hourly,
  intraday = [],
  intradayLabel = null,
  levels = [],
  overlays = {},
  markers = {},
}: {
  daily: Candle[];
  hourly: Candle[];
  intraday?: Candle[];
  intradayLabel?: string | null;
  levels?: Level[];
  compact?: boolean;
  overlays?: Record<string, ChartOverlays>;
  markers?: Record<string, ChartMarker[]>;
}) {
  const intradayAvailable = (intraday?.length || 0) > 0 && Boolean(intradayLabel);
  const [timeframe, setTimeframe] = useState<Timeframe>(intradayAvailable ? "intraday" : "daily");
  const [mode, setMode] = useState<Mode>("swing");
  const [toggles, setToggles] = useState<ToggleState>(DEFAULT_TOGGLES);
  const candles = timeframe === "daily" ? daily : timeframe === "hourly" ? hourly : intraday;
  const overlayKey = timeframe === "intraday" ? intradayLabel || "intraday" : timeframe;
  const activeOverlays = useMemo(() => overlays[overlayKey] || {}, [overlays, overlayKey]);
  const activeMarkers = useMemo(() => markers[overlayKey] || [], [markers, overlayKey]);

  const components = useMemo(
    () => ({
      chartPanel: (props: IDockviewPanelProps<{ panel: ChartPanelId }>) => (
        <div className="h-full overflow-hidden p-1.5">
          <ChartPanel panel={props.params.panel} candles={candles} levels={(activeOverlays.levels as Level[]) || levels} overlays={activeOverlays} markers={activeMarkers} toggles={toggles} mode={mode} />
        </div>
      ),
    }),
    [candles, activeOverlays, activeMarkers, levels, toggles, mode],
  );

  function onReady(event: DockviewReadyEvent) {
    seedChartLayout(event.api);
  }

  return (
    <section className="flex h-full min-h-[560px] flex-col overflow-hidden">
      <div className="flex min-h-9 flex-wrap items-center justify-between gap-2 border-b border-white/10 px-2 py-1.5">
        <div className="flex items-center gap-1.5">
          <Segmented
            value={timeframe}
            onChange={setTimeframe}
            items={[
              { value: "daily", label: "Daily" },
              { value: "hourly", label: "Hourly" },
              ...(intradayAvailable ? [{ value: "intraday" as Timeframe, label: intradayLabel || "Intraday" }] : []),
            ]}
          />
          <Segmented value={mode} onChange={setMode} items={[{ value: "swing", label: "Swing Desk" }, { value: "quant", label: "Quant Lab" }]} />
        </div>
        <div className="flex flex-wrap items-center gap-1">
          <Toggle label="MA" active={toggles.ma} onClick={() => setToggles((value) => ({ ...value, ma: !value.ma }))} />
          <Toggle label="VWAP" active={toggles.vwap} onClick={() => setToggles((value) => ({ ...value, vwap: !value.vwap }))} />
          <Toggle label="ST" active={toggles.supertrend} onClick={() => setToggles((value) => ({ ...value, supertrend: !value.supertrend }))} />
          <Toggle label="BB/KC" active={toggles.bbkc} onClick={() => setToggles((value) => ({ ...value, bbkc: !value.bbkc }))} />
          <Toggle label="Levels" active={toggles.levels} onClick={() => setToggles((value) => ({ ...value, levels: !value.levels }))} />
          <Toggle label="Marks" active={toggles.breakouts || toggles.divergences || toggles.volumeSpikes} onClick={() => setToggles((value) => ({ ...value, breakouts: !value.breakouts, divergences: !value.divergences, volumeSpikes: !value.volumeSpikes }))} />
        </div>
      </div>
      <div className="min-h-0 flex-1">
        <DockviewReact components={components} onReady={onReady} theme={themeAbyss} />
      </div>
    </section>
  );
}

function ChartPanel({ panel, candles, overlays, markers, levels, toggles, mode }: { panel: ChartPanelId; candles: Candle[]; overlays: ChartOverlays; markers: ChartMarker[]; levels: Level[]; toggles: ToggleState; mode: Mode }) {
  if (panel === "price_action") return <PriceActionChart candles={candles} overlays={overlays} markers={markers} levels={levels} toggles={toggles} mode={mode} />;
  if (panel === "volume") return <VolumeChart candles={candles} overlays={overlays} markers={markers} toggles={toggles} />;
  if (panel === "momentum") return <MomentumChart candles={candles} overlays={overlays} />;
  if (panel === "volatility") return <VolatilityChart candles={candles} overlays={overlays} />;
  return <LevelPanel levels={levels} />;
}

function PriceActionChart({ candles, overlays, markers, levels, toggles, mode }: { candles: Candle[]; overlays: ChartOverlays; markers: ChartMarker[]; levels: Level[]; toggles: ToggleState; mode: Mode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = baseChart(ref.current);
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22C55E",
      downColor: "#EF4444",
      borderVisible: false,
      wickUpColor: "#22C55E",
      wickDownColor: "#EF4444",
    });
    candleSeries.setData(candles.map((candle) => ({ time: candle.timestamp as Time, open: candle.open, high: candle.high, low: candle.low, close: candle.close })));

    if (toggles.ma) {
      addLine(chart, overlays.ma20, "#22C55E", 1);
      addLine(chart, overlays.ma50, "#3B82F6", 1);
      addLine(chart, overlays.ma200, "#EAB308", 1);
    }
    if (toggles.vwap) addLine(chart, overlays.vwap, "#A78BFA", 1);
    if (toggles.supertrend) addLine(chart, overlays.supertrend, "#06B6D4", 1);
    if (toggles.bbkc) {
      addLine(chart, overlays.bollinger?.upper, "rgba(59,130,246,0.5)", 1);
      addLine(chart, overlays.bollinger?.lower, "rgba(59,130,246,0.5)", 1);
      addLine(chart, overlays.keltner?.upper, "rgba(234,179,8,0.5)", 1);
      addLine(chart, overlays.keltner?.lower, "rgba(234,179,8,0.5)", 1);
    }
    if (toggles.levels) {
      levels.forEach((level) => {
        candleSeries.createPriceLine({ price: level.level, color: level.type === "support" ? "#22C55E" : "#EF4444", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: `${level.type[0].toUpperCase()} ${level.strength}` });
      });
    }
    const filtered = markers.filter((marker) => (marker.type === "volume_spike" && toggles.volumeSpikes) || (marker.type === "divergence" && toggles.divergences) || (marker.type.includes("break") && toggles.breakouts));
    if (filtered.length) createSeriesMarkers(candleSeries, filtered.map(toSeriesMarker));
    chart.timeScale().fitContent();
    return cleanupChart(chart, ref.current);
  }, [candles, overlays, markers, levels, toggles, mode]);
  return <ChartFrame title="Price Action" icon={<BarChart3 size={14} />} subtitle={mode === "swing" ? "Entry, stop, targets, levels" : "Signal validation surface"} refEl={ref} />;
}

function VolumeChart({ candles, overlays, markers, toggles }: { candles: Candle[]; overlays: ChartOverlays; markers: ChartMarker[]; toggles: ToggleState }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = baseChart(ref.current);
    const volume = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "" });
    volume.setData(candles.map((candle) => ({ time: candle.timestamp as Time, value: candle.volume, color: candle.close >= candle.open ? "rgba(34,197,94,0.45)" : "rgba(239,68,68,0.45)" })));
    addLine(chart, overlays.volume_avg20, "#3B82F6", 1);
    if (toggles.volumeSpikes) createSeriesMarkers(volume, markers.filter((marker) => marker.type === "volume_spike").map(toSeriesMarker));
    chart.timeScale().fitContent();
    return cleanupChart(chart, ref.current);
  }, [candles, overlays, markers, toggles.volumeSpikes]);
  return <ChartFrame title="Volume" icon={<Activity size={14} />} subtitle="Expansion and anomaly markers" refEl={ref} />;
}

function MomentumChart({ overlays }: { candles: Candle[]; overlays: ChartOverlays }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = baseChart(ref.current);
    addLine(chart, overlays.rsi, "#22C55E", 2);
    addLine(chart, overlays.stoch_rsi_k, "#3B82F6", 1);
    addLine(chart, overlays.stoch_rsi_d, "#EAB308", 1);
    chart.timeScale().fitContent();
    return cleanupChart(chart, ref.current);
  }, [overlays]);
  return <ChartFrame title="Momentum" icon={<Activity size={14} />} subtitle={`MACD: ${overlays.macd_state?.state || "-"}`} refEl={ref} />;
}

function VolatilityChart({ overlays }: { candles: Candle[]; overlays: ChartOverlays }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = baseChart(ref.current);
    addLine(chart, overlays.bollinger?.upper, "#3B82F6", 1);
    addLine(chart, overlays.bollinger?.lower, "#3B82F6", 1);
    addLine(chart, overlays.keltner?.upper, "#EAB308", 1);
    addLine(chart, overlays.keltner?.lower, "#EAB308", 1);
    chart.timeScale().fitContent();
    return cleanupChart(chart, ref.current);
  }, [overlays]);
  return <ChartFrame title="Volatility" icon={<Activity size={14} />} subtitle="Bollinger / Keltner squeeze map" refEl={ref} />;
}

function LevelPanel({ levels }: { levels: Level[] }) {
  return (
    <section className="panel h-full overflow-auto">
      <div className="panel-header">
        <strong>Levels</strong>
        <span className="muted">{levels.length} clusters</span>
      </div>
      <div className="panel-body grid gap-1.5">
        {levels.map((level) => (
          <div className="grid grid-cols-[1fr_auto] items-center gap-3 border-b border-white/10 py-2 text-sm" key={`${level.type}-${level.level}`}>
            <div>
              <strong className={level.type === "support" ? "text-emerald-300" : "text-rose-300"}>{level.level}</strong>
              <span className="ml-2 text-[11px] uppercase text-slate-500">{level.type} · {level.breakout_state || "watch"}</span>
            </div>
            <div className="text-right text-[11px] text-slate-400">
              <div>strength {level.strength} · recency {level.recency_score ?? "-"}</div>
              <div>{level.touches} touches · {level.distance_pct}% · vol {level.volume_score ?? "-"}</div>
            </div>
          </div>
        ))}
        {levels.length === 0 ? <p className="muted">No levels available.</p> : null}
      </div>
    </section>
  );
}

function ChartFrame({ title, subtitle, icon, refEl }: { title: string; subtitle: string; icon: ReactNode; refEl: RefObject<HTMLDivElement | null> }) {
  return (
    <section className="panel flex h-full min-h-[280px] flex-col">
      <div className="panel-header">
        <div className="flex items-center gap-2">
          {icon}
          <strong>{title}</strong>
        </div>
        <span className="muted">{subtitle}</span>
      </div>
      <div className="min-h-0 flex-1" ref={refEl} />
    </section>
  );
}

function baseChart(container: HTMLElement): IChartApi {
  const chart = createChart(container, {
    autoSize: true,
    layout: { background: { type: ColorType.Solid, color: "#0A0A0A" }, textColor: "#A1A1AA" },
    grid: { vertLines: { color: "rgba(145,164,173,0.08)" }, horzLines: { color: "rgba(145,164,173,0.08)" } },
    rightPriceScale: { borderColor: "rgba(145,164,173,0.12)" },
    timeScale: { borderColor: "rgba(145,164,173,0.12)", timeVisible: true },
    crosshair: { mode: 1 },
  });
  return chart;
}

function addLine(chart: IChartApi, points: Array<{ time: number; value: number | null | undefined }> | undefined, color: string, width: 1 | 2) {
  if (!points?.length) return undefined;
  const data = points
    .map((point) => ({ time: Number(point.time), value: Number(point.value) }))
    .filter((point) => Number.isFinite(point.time) && Number.isFinite(point.value));
  if (!data.length) return undefined;
  const series = chart.addSeries(LineSeries, { color, lineWidth: width, priceLineVisible: false, lastValueVisible: false }) as ISeriesApi<"Line">;
  series.setData(data.map((point) => ({ time: point.time as Time, value: point.value })));
  return series;
}

function toSeriesMarker(marker: ChartMarker): SeriesMarker<Time> {
  return { time: marker.time as Time, position: marker.position, color: marker.color, shape: marker.position === "belowBar" ? "arrowUp" : "arrowDown", text: marker.text };
}

function cleanupChart(chart: IChartApi, container: HTMLDivElement | null) {
  return () => {
    chart.remove();
    if (container) container.innerHTML = "";
  };
}

function seedChartLayout(api: DockviewApi) {
  api.addPanel({ id: "price_action", title: "Price Action", component: "chartPanel", params: { panel: "price_action" }, minimumWidth: 360, minimumHeight: 280 });
  api.addPanel({ id: "volume", title: "Volume", component: "chartPanel", params: { panel: "volume" }, position: { referencePanel: "price_action", direction: "below" }, initialHeight: 190 });
  api.addPanel({ id: "momentum", title: "Momentum", component: "chartPanel", params: { panel: "momentum" }, position: { referencePanel: "price_action", direction: "right" }, initialWidth: 340 });
  api.addPanel({ id: "volatility", title: "Volatility", component: "chartPanel", params: { panel: "volatility" }, position: { referencePanel: "momentum", direction: "within" } });
  api.addPanel({ id: "levels", title: "Levels", component: "chartPanel", params: { panel: "levels" }, position: { referencePanel: "volume", direction: "within" } });
}

function Segmented<T extends string>({ value, onChange, items }: { value: T; onChange: (value: T) => void; items: Array<{ value: T; label: string }> }) {
  return (
    <div className="flex overflow-hidden rounded-md border border-white/10 bg-white/[0.025]">
      {items.map((item) => (
        <button key={item.value} type="button" className={item.value === value ? "h-7 min-h-0 bg-emerald-400/15 px-2 text-xs font-semibold text-emerald-300" : "h-7 min-h-0 bg-transparent px-2 text-xs font-semibold text-slate-400 hover:bg-white/[0.04]"} onClick={() => onChange(item.value)}>
          {item.label}
        </button>
      ))}
    </div>
  );
}

function Toggle({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button type="button" className={active ? "h-7 min-h-0 rounded border border-emerald-400/30 bg-emerald-400/10 px-2 text-[11px] font-semibold text-emerald-300" : "h-7 min-h-0 rounded border border-white/10 bg-white/[0.025] px-2 text-[11px] font-semibold text-slate-500 hover:text-slate-200"} onClick={onClick}>
      {label}
    </button>
  );
}
