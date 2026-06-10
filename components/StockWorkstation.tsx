"use client";

import {
  DockviewReact,
  type BuiltInContextMenuItem,
  type DockviewReadyEvent,
  type GetTabContextMenuItemsParams,
  type IDockviewHeaderActionsProps,
  type IDockviewPanelProps,
  themeAbyss,
} from "dockview";
import { Plus, RotateCcw } from "lucide-react";
import { useMemo, useState } from "react";
import { STOCK_PANELS, StockPanelContent, type StockPanelId } from "@/components/StockPanelContent";
import { useWorkstation } from "@/components/WorkstationContext";
import type { StockAnalysis, Timeframe } from "@/lib/types";

export function StockWorkstation({ analysis }: { analysis: StockAnalysis; timeframe?: Timeframe }) {
  const workstation = useWorkstation();

  const HeaderActions = useMemo(
    () =>
      function HeaderActions(props: IDockviewHeaderActionsProps) {
        const [open, setOpen] = useState(false);
        if (!props.isGroupActive) return null;

        return (
          <div className="relative mr-1 flex items-center gap-1">
            <button
              type="button"
              className="btn-icon"
              onClick={(event) => {
                event.stopPropagation();
                setOpen((value) => !value);
              }}
              title="Add panel"
            >
              <Plus size={14} />
            </button>
            {open ? (
              <div className="absolute right-0 top-7 z-50 w-44 overflow-hidden rounded-md border border-white/10 bg-[#141416] py-1 shadow-none border border-white/[0.06]">
                {STOCK_PANELS.map((panel) => (
                  <button
                    key={panel.id}
                    type="button"
                    className="flex h-8 min-h-0 w-full items-center justify-start rounded-none border-0 bg-transparent px-3 py-0 text-left text-xs font-semibold text-slate-300 hover:bg-emerald-400/10 hover:text-emerald-200"
                    onClick={(event) => {
                      event.stopPropagation();
                      openPanel(props, panel.id);
                      setOpen(false);
                    }}
                  >
                    {panel.title}
                  </button>
                ))}
              </div>
            ) : null}
            <button
              type="button"
              className="btn-icon"
              onClick={(event) => {
                event.stopPropagation();
                workstation?.resetActive();
              }}
              title="Reset workspace layout"
            >
              <RotateCcw size={12} />
            </button>
          </div>
        );
      },
    [workstation],
  );

  const components = useMemo(
    () => ({
      stockPanel: (props: IDockviewPanelProps<{ panel: StockPanelId }>) => (
        <div className="dockview-panel-scroll h-full overflow-auto p-1.5">
          <StockPanelContent panel={props.params.panel} analysis={analysis} />
        </div>
      ),
    }),
    [analysis],
  );

  function onReady(event: DockviewReadyEvent) {
    workstation?.setDockApi(event.api);
    workstation?.loadActiveWorkspace(event.api);
  }

  const daily = analysis.daily_analysis || {};
  const risk = analysis.risk_plan || {};

  return (
    <section className="terminal-workstation">
      <div className="terminal-tape">
        <div className="terminal-tape-title">
          <span>Decision Engine</span>
          <strong>{analysis.symbol}</strong>
        </div>
        <TapeMetric label="Last" value={fmt(daily.last_price)} hot />
        <TapeMetric label="Trend" value={daily.trend_state || "-"} />
        <TapeMetric label="Score" value={fmt(daily.technical_score)} hot />
        <TapeMetric label="RSI" value={fmt(daily.rsi)} />
        <TapeMetric label="R:R" value={fmt(daily.risk_reward)} />
        <TapeMetric label="Risk Qty" value={fmt(risk.estimated_quantity)} />
        <TapeMetric label="Source" value={analysis.data_source?.daily?.provider || "cache"} />
      </div>
      <section className="dock-workstation dockview-theme-abyss h-[calc(100vh-88px)] min-h-[680px] w-full overflow-hidden">
        <DockviewReact
          components={components}
          getTabContextMenuItems={getTabContextMenuItems}
          onReady={onReady}
          popoutUrl="/popout.html"
          rightHeaderActionsComponent={HeaderActions}
          theme={themeAbyss}
        />
      </section>
    </section>
  );
}

function TapeMetric({ label, value, hot = false }: { label: string; value: unknown; hot?: boolean }) {
  return (
    <div className={hot ? "terminal-tape-metric hot" : "terminal-tape-metric"}>
      <span>{label}</span>
      <strong>{String(value ?? "-")}</strong>
    </div>
  );
}

function openPanel(props: IDockviewHeaderActionsProps, panel: StockPanelId) {
  const existing = props.containerApi.getPanel(panel);
  if (existing) {
    existing.api.moveTo({ group: props.group });
    return;
  }

  props.containerApi.addPanel({
    id: panel,
    title: STOCK_PANELS.find((item) => item.id === panel)?.title || panel,
    component: "stockPanel",
    params: { panel },
    position: { referenceGroup: props.group, direction: "within" },
  });
}

function getTabContextMenuItems(params: GetTabContextMenuItemsParams): BuiltInContextMenuItem[] | Array<BuiltInContextMenuItem | { label: string; action: () => void }> {
  return [
    {
      label: "Pop out group",
      action: () => {
        void params.api.addPopoutGroup(params.group, { popoutUrl: "/popout.html" });
      },
    },
    "separator",
    "close",
    "closeOthers",
    "closeAll",
  ];
}

function fmt(value: unknown) {
  return typeof value === "number" ? value.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : value ?? "-";
}
