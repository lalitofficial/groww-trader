"use client";

import type { DockviewApi } from "dockview";
import { useCallback, useContext, useMemo, useRef, useState, createContext, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { STOCK_PANELS, type StockPanelId } from "@/components/StockPanelContent";
import type { Timeframe } from "@/lib/types";

export const TIMEFRAME_OPTIONS: Timeframe[] = ["daily", "hourly", "30m", "15m", "5m"];

const WORKSPACES_KEY = "groww-dockview-decision-workspaces-v1";
const ACTIVE_WORKSPACE_KEY = "groww-dockview-active-decision-workspace-v1";

type WorkspacePreset = "decision" | "intraday" | "chart" | "risk" | "research" | "multi" | "custom";
type DockLayout = ReturnType<DockviewApi["toJSON"]>;

export type SavedWorkspace = {
  id: string;
  name: string;
  preset: WorkspacePreset;
  layout?: DockLayout;
  updatedAt?: string;
};

export type WorkstationContextValue = {
  api: DockviewApi | null;
  workspaces: SavedWorkspace[];
  activeWorkspaceId: string;
  workspaceDraftName: string;
  timeframe: Timeframe;
  status: string;
  setWorkspaceDraftName: (value: string) => void;
  switchWorkspace: (workspaceId: string) => void;
  saveActive: () => void;
  createNew: () => void;
  resetActive: () => void;
  deleteActive: () => void;
  setTimeframe: (timeframe: Timeframe) => void;
  setDockApi: (api: DockviewApi) => void;
  loadActiveWorkspace: (api?: DockviewApi) => void;
  openPanel: (panel: StockPanelId) => void;
};

const DEFAULT_WORKSPACES: SavedWorkspace[] = [
  { id: "intraday-desk", name: "Intraday Desk", preset: "intraday" },
  { id: "decision-desk", name: "Swing Desk", preset: "decision" },
  { id: "chart-desk", name: "Chart Desk", preset: "chart" },
  { id: "risk-desk", name: "Risk Desk", preset: "risk" },
  { id: "research-desk", name: "Research Desk", preset: "research" },
  { id: "multi-monitor", name: "Multi Monitor", preset: "multi" },
];

const WorkstationContext = createContext<WorkstationContextValue | null>(null);

export function WorkstationProvider({
  children,
  symbol,
  timeframe,
}: {
  children: ReactNode;
  symbol: string;
  timeframe: Timeframe;
}) {
  const router = useRouter();
  const apiRef = useRef<DockviewApi | null>(null);
  const initialWorkspaces = useMemo(() => readWorkspaces(), []);
  const [workspaces, setWorkspaces] = useState<SavedWorkspace[]>(initialWorkspaces);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState(() => readActiveWorkspaceId(initialWorkspaces));
  const [workspaceDraftName, setWorkspaceDraftName] = useState(() => workspaceName(initialWorkspaces, readActiveWorkspaceId(initialWorkspaces)));
  const [status, setStatus] = useState("");

  const loadWorkspace = useCallback((workspace: SavedWorkspace, api = apiRef.current) => {
    if (!api) return;
    api.clear();
    if (workspace.layout) {
      try {
        api.fromJSON(workspace.layout, { reuseExistingPanels: false });
        return;
      } catch {
        // Older saved layouts can reference retired panels; fall back to the preset.
      }
    }
    seedLayout(api, workspace.preset);
  }, []);

  const loadActiveWorkspace = useCallback((api = apiRef.current) => {
    const stored = readWorkspaces();
    const activeId = readActiveWorkspaceId(stored);
    const workspace = stored.find((item) => item.id === activeId) || stored[0] || DEFAULT_WORKSPACES[0];
    setWorkspaces(stored);
    setActiveWorkspaceId(workspace.id);
    setWorkspaceDraftName(workspace.name);
    setStatus("");
    loadWorkspace(workspace, api);
  }, [loadWorkspace]);

  const setDockApi = useCallback((api: DockviewApi) => {
    apiRef.current = api;
  }, []);

  const switchWorkspace = useCallback((workspaceId: string) => {
    const workspace = workspaces.find((item) => item.id === workspaceId) || workspaces[0] || DEFAULT_WORKSPACES[0];
    setActiveWorkspaceId(workspace.id);
    setWorkspaceDraftName(workspace.name);
    setStatus("");
    writeActiveWorkspaceId(workspace.id);
    loadWorkspace(workspace);
  }, [loadWorkspace, workspaces]);

  const saveActive = useCallback(() => {
    const api = apiRef.current;
    if (!api) return;
    const now = new Date().toISOString();
    const next = workspaces.map((workspace) =>
      workspace.id === activeWorkspaceId
        ? {
            ...workspace,
            name: workspaceDraftName.trim() || workspace.name,
            layout: api.toJSON(),
            updatedAt: now,
          }
        : workspace,
    );
    writeWorkspaces(next);
    setWorkspaces(next);
    setStatus("Saved");
  }, [activeWorkspaceId, workspaceDraftName, workspaces]);

  const createNew = useCallback(() => {
    const api = apiRef.current;
    if (!api) return;
    const baseName = workspaceDraftName.trim() || `Workspace ${workspaces.length + 1}`;
    const id = `${slugify(baseName)}-${Date.now().toString(36)}`;
    const workspace: SavedWorkspace = {
      id,
      name: uniqueWorkspaceName(baseName, workspaces),
      preset: "custom",
      layout: api.toJSON(),
      updatedAt: new Date().toISOString(),
    };
    const next = [...workspaces, workspace];
    writeWorkspaces(next);
    writeActiveWorkspaceId(id);
    setWorkspaces(next);
    setActiveWorkspaceId(id);
    setWorkspaceDraftName(workspace.name);
    setStatus("Created");
  }, [workspaceDraftName, workspaces]);

  const resetActive = useCallback(() => {
    const workspace = workspaces.find((item) => item.id === activeWorkspaceId) || DEFAULT_WORKSPACES[0];
    const api = apiRef.current;
    if (!api) return;
    api.clear();
    seedLayout(api, workspace.preset === "custom" ? "decision" : workspace.preset);
    setStatus("Reset loaded");
  }, [activeWorkspaceId, workspaces]);

  const deleteActive = useCallback(() => {
    if (DEFAULT_WORKSPACES.some((workspace) => workspace.id === activeWorkspaceId)) {
      setStatus("Preset kept");
      return;
    }
    const next = workspaces.filter((workspace) => workspace.id !== activeWorkspaceId);
    const fallback = next[0] || DEFAULT_WORKSPACES[0];
    writeWorkspaces(next);
    writeActiveWorkspaceId(fallback.id);
    setWorkspaces(next);
    setActiveWorkspaceId(fallback.id);
    setWorkspaceDraftName(fallback.name);
    setStatus("Deleted");
    loadWorkspace(fallback);
  }, [activeWorkspaceId, loadWorkspace, workspaces]);

  const setTimeframe = useCallback((next: Timeframe) => {
    if (next === timeframe) return;
    router.push(`/stock/${symbol}?timeframe=${next}`);
  }, [router, symbol, timeframe]);

  const openPanel = useCallback((panel: StockPanelId) => {
    const api = apiRef.current;
    if (!api) return;
    const existing = api.getPanel(panel);
    if (existing) {
      (existing.api as unknown as { setActive?: () => void }).setActive?.();
      return;
    }
    api.addPanel({
      id: panel,
      title: STOCK_PANELS.find((item) => item.id === panel)?.title || panel,
      component: "stockPanel",
      params: { panel },
    });
  }, []);

  const value = useMemo<WorkstationContextValue>(
    () => ({
      api: apiRef.current,
      workspaces,
      activeWorkspaceId,
      workspaceDraftName,
      timeframe,
      status,
      setWorkspaceDraftName,
      switchWorkspace,
      saveActive,
      createNew,
      resetActive,
      deleteActive,
      setTimeframe,
      setDockApi,
      loadActiveWorkspace,
      openPanel,
    }),
    [
      activeWorkspaceId,
      createNew,
      deleteActive,
      loadActiveWorkspace,
      openPanel,
      resetActive,
      saveActive,
      setDockApi,
      setTimeframe,
      status,
      switchWorkspace,
      timeframe,
      workspaceDraftName,
      workspaces,
    ],
  );

  return <WorkstationContext.Provider value={value}>{children}</WorkstationContext.Provider>;
}

export function useWorkstation() {
  return useContext(WorkstationContext);
}

function seedLayout(api: DockviewApi, preset: WorkspacePreset = "decision") {
  if (preset === "intraday") return seedIntradayLayout(api);
  if (preset === "chart") return seedChartFocusLayout(api);
  if (preset === "risk") return seedRiskLayout(api);
  if (preset === "research") return seedResearchLayout(api);
  if (preset === "multi") return seedMultiMonitorLayout(api);

  api.addPanel({ id: "decision", title: "Decision", component: "stockPanel", params: { panel: "decision" }, minimumWidth: 320, minimumHeight: 280 });
  api.addPanel({
    id: "tradingview",
    title: "Chart",
    component: "stockPanel",
    params: { panel: "tradingview" },
    position: { referencePanel: "decision", direction: "right" },
    minimumWidth: 520,
    minimumHeight: 340,
  });
  api.addPanel({ id: "resistances", title: "Levels", component: "stockPanel", params: { panel: "resistances" }, position: { referencePanel: "tradingview", direction: "below" }, initialHeight: 300 });
  api.addPanel({ id: "metrics", title: "Risk", component: "stockPanel", params: { panel: "metrics" }, position: { referencePanel: "decision", direction: "below" }, initialHeight: 180 });
  api.addPanel({ id: "ai", title: "AI Read", component: "stockPanel", params: { panel: "ai" }, position: { referencePanel: "tradingview", direction: "right" }, initialWidth: 360, minimumWidth: 310 });
  api.addPanel({ id: "account", title: "Position", component: "stockPanel", params: { panel: "account" }, position: { referencePanel: "ai", direction: "below" }, initialHeight: 210 });
  api.addPanel({ id: "trade_plan", title: "Plan", component: "stockPanel", params: { panel: "trade_plan" }, position: { referencePanel: "decision", direction: "within" } });
}

function seedIntradayLayout(api: DockviewApi) {
  api.addPanel({ id: "tradingview", title: "Chart", component: "stockPanel", params: { panel: "tradingview" }, minimumWidth: 560, minimumHeight: 360 });
  api.addPanel({ id: "intraday", title: "Intraday", component: "stockPanel", params: { panel: "intraday" }, position: { referencePanel: "tradingview", direction: "right" }, initialWidth: 380 });
  api.addPanel({ id: "decision", title: "Decision", component: "stockPanel", params: { panel: "decision" }, position: { referencePanel: "intraday", direction: "below" }, initialHeight: 320 });
  api.addPanel({ id: "trade_plan", title: "Plan", component: "stockPanel", params: { panel: "trade_plan" }, position: { referencePanel: "decision", direction: "within" } });
  api.addPanel({ id: "resistances", title: "Levels", component: "stockPanel", params: { panel: "resistances" }, position: { referencePanel: "tradingview", direction: "below" }, initialHeight: 260 });
  api.addPanel({ id: "paper", title: "Paper", component: "stockPanel", params: { panel: "paper" }, position: { referencePanel: "resistances", direction: "right" }, initialWidth: 460 });
  api.addPanel({ id: "ai", title: "AI", component: "stockPanel", params: { panel: "ai" }, position: { referencePanel: "intraday", direction: "within" } });
  api.addPanel({ id: "news", title: "Catalysts", component: "stockPanel", params: { panel: "news" }, position: { referencePanel: "ai", direction: "within" } });
  api.addPanel({ id: "account", title: "Account", component: "stockPanel", params: { panel: "account" }, position: { referencePanel: "paper", direction: "within" } });
}

function seedChartFocusLayout(api: DockviewApi) {
  api.addPanel({ id: "tradingview", title: "Live Chart", component: "stockPanel", params: { panel: "tradingview" }, minimumWidth: 650, minimumHeight: 360 });
  api.addPanel({ id: "charts", title: "Market Map", component: "stockPanel", params: { panel: "charts" }, position: { referencePanel: "tradingview", direction: "below" }, initialHeight: 440 });
  api.addPanel({ id: "decision", title: "Decision", component: "stockPanel", params: { panel: "decision" }, position: { referencePanel: "tradingview", direction: "right" }, initialWidth: 360 });
  api.addPanel({ id: "resistances", title: "Levels", component: "stockPanel", params: { panel: "resistances" }, position: { referencePanel: "decision", direction: "below" }, initialHeight: 300 });
  api.addPanel({ id: "ai", title: "AI Tape", component: "stockPanel", params: { panel: "ai" }, position: { referencePanel: "resistances", direction: "within" } });
  api.addPanel({ id: "quant", title: "Quant Lab", component: "stockPanel", params: { panel: "quant" }, position: { referencePanel: "charts", direction: "within" } });
}

function seedRiskLayout(api: DockviewApi) {
  api.addPanel({ id: "decision", title: "Decision", component: "stockPanel", params: { panel: "decision" }, minimumWidth: 320, minimumHeight: 300 });
  api.addPanel({ id: "account", title: "Position & Alerts", component: "stockPanel", params: { panel: "account" }, position: { referencePanel: "decision", direction: "right" }, initialWidth: 430 });
  api.addPanel({ id: "metrics", title: "Risk Matrix", component: "stockPanel", params: { panel: "metrics" }, position: { referencePanel: "decision", direction: "below" }, initialHeight: 210 });
  api.addPanel({ id: "resistances", title: "Levels", component: "stockPanel", params: { panel: "resistances" }, position: { referencePanel: "account", direction: "below" }, initialHeight: 320 });
  api.addPanel({ id: "tradingview", title: "Chart", component: "stockPanel", params: { panel: "tradingview" }, position: { referencePanel: "metrics", direction: "below" }, initialHeight: 330 });
  api.addPanel({ id: "ai", title: "Risk Read", component: "stockPanel", params: { panel: "ai" }, position: { referencePanel: "resistances", direction: "within" } });
}

function seedResearchLayout(api: DockviewApi) {
  api.addPanel({ id: "ai", title: "AI Research", component: "stockPanel", params: { panel: "ai" }, minimumWidth: 420, minimumHeight: 360 });
  api.addPanel({ id: "news", title: "Catalysts", component: "stockPanel", params: { panel: "news" }, position: { referencePanel: "ai", direction: "right" }, initialWidth: 380 });
  api.addPanel({ id: "quant", title: "Backtests", component: "stockPanel", params: { panel: "quant" }, position: { referencePanel: "ai", direction: "below" }, initialHeight: 260 });
  api.addPanel({ id: "diagnostics", title: "Diagnostics", component: "stockPanel", params: { panel: "diagnostics" }, position: { referencePanel: "news", direction: "below" }, initialHeight: 320 });
  api.addPanel({ id: "decision", title: "Decision", component: "stockPanel", params: { panel: "decision" }, position: { referencePanel: "quant", direction: "left" }, initialWidth: 340 });
  api.addPanel({ id: "charts", title: "Market Map", component: "stockPanel", params: { panel: "charts" }, position: { referencePanel: "quant", direction: "within" } });
}

function seedMultiMonitorLayout(api: DockviewApi) {
  api.addPanel({ id: "tradingview", title: "Live Chart", component: "stockPanel", params: { panel: "tradingview" }, minimumWidth: 560, minimumHeight: 340 });
  api.addPanel({ id: "charts", title: "Market Map", component: "stockPanel", params: { panel: "charts" }, position: { referencePanel: "tradingview", direction: "below" }, initialHeight: 420 });
  api.addPanel({ id: "quant", title: "Quant Lab", component: "stockPanel", params: { panel: "quant" }, position: { referencePanel: "charts", direction: "below" }, initialHeight: 190 });
  api.addPanel({ id: "ai", title: "AI Tape", component: "stockPanel", params: { panel: "ai" }, position: { referencePanel: "tradingview", direction: "right" }, initialWidth: 390 });
  api.addPanel({ id: "resistances", title: "Levels", component: "stockPanel", params: { panel: "resistances" }, position: { referencePanel: "ai", direction: "below" }, initialHeight: 320 });
  api.addPanel({ id: "account", title: "Account", component: "stockPanel", params: { panel: "account" }, position: { referencePanel: "resistances", direction: "below" }, initialHeight: 230 });
  api.addPanel({ id: "news", title: "News", component: "stockPanel", params: { panel: "news" }, position: { referencePanel: "account", direction: "within" } });
  api.addPanel({ id: "decision", title: "Decision", component: "stockPanel", params: { panel: "decision" }, position: { referencePanel: "tradingview", direction: "left" }, initialWidth: 330 });
  api.addPanel({ id: "metrics", title: "Risk Matrix", component: "stockPanel", params: { panel: "metrics" }, position: { referencePanel: "decision", direction: "below" }, initialHeight: 180 });
  api.addPanel({ id: "trade_plan", title: "Plan", component: "stockPanel", params: { panel: "trade_plan" }, position: { referencePanel: "decision", direction: "within" } });
}

function readWorkspaces(): SavedWorkspace[] {
  if (typeof window === "undefined") return DEFAULT_WORKSPACES;
  try {
    const parsed = JSON.parse(window.localStorage.getItem(WORKSPACES_KEY) || "[]");
    if (!Array.isArray(parsed)) return DEFAULT_WORKSPACES;
    return mergeDefaultWorkspaces(parsed.filter(isWorkspace));
  } catch {
    return DEFAULT_WORKSPACES;
  }
}

function writeWorkspaces(workspaces: SavedWorkspace[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(WORKSPACES_KEY, JSON.stringify(workspaces));
}

function readActiveWorkspaceId(workspaces: SavedWorkspace[]) {
  if (typeof window === "undefined") return workspaces[0]?.id || DEFAULT_WORKSPACES[0].id;
  const activeId = window.localStorage.getItem(ACTIVE_WORKSPACE_KEY);
  return workspaces.some((workspace) => workspace.id === activeId) ? activeId || workspaces[0].id : workspaces[0]?.id || DEFAULT_WORKSPACES[0].id;
}

function writeActiveWorkspaceId(id: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ACTIVE_WORKSPACE_KEY, id);
}

function workspaceName(workspaces: SavedWorkspace[], id: string) {
  return workspaces.find((workspace) => workspace.id === id)?.name || workspaces[0]?.name || "Terminal";
}

function mergeDefaultWorkspaces(workspaces: SavedWorkspace[]) {
  const byId = new Map(workspaces.map((workspace) => [workspace.id, workspace]));
  return [
    ...DEFAULT_WORKSPACES.map((workspace) => ({ ...workspace, ...byId.get(workspace.id), preset: workspace.preset })),
    ...workspaces.filter((workspace) => !DEFAULT_WORKSPACES.some((preset) => preset.id === workspace.id)),
  ];
}

function isWorkspace(value: unknown): value is SavedWorkspace {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<SavedWorkspace>;
  return typeof item.id === "string" && typeof item.name === "string";
}

function slugify(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "workspace";
}

function uniqueWorkspaceName(name: string, workspaces: SavedWorkspace[]) {
  const existing = new Set(workspaces.map((workspace) => workspace.name));
  if (!existing.has(name)) return name;
  let index = 2;
  while (existing.has(`${name} ${index}`)) index += 1;
  return `${name} ${index}`;
}
