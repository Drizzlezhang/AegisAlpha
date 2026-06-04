import { create } from "zustand";
import type { PipelineEvent } from "@/lib/types";

interface PipelineStore {
  isRunning: boolean;
  pipelineMode: "full" | "lightweight" | null;
  pipelineRunId: number | null;
  agentStatuses: Record<string, "running" | "done" | "error" | "skipped">;
  events: PipelineEvent[];
  isConnected: boolean;

  connect: () => void;
  disconnect: () => void;
  handleEvent: (event: PipelineEvent) => void;
  clearEvents: () => void;
}

export const usePipelineStore = create<PipelineStore>((set) => ({
  isRunning: false,
  pipelineMode: null,
  pipelineRunId: null,
  agentStatuses: {},
  events: [],
  isConnected: false,

  connect: () => set({ isConnected: true }),
  disconnect: () => set({ isConnected: false }),

  handleEvent: (event: PipelineEvent) =>
    set((state) => {
      const newStatuses = { ...state.agentStatuses };
      if (event.agent_name) {
        switch (event.type) {
          case "agent_start":
            newStatuses[event.agent_name] = "running";
            break;
          case "agent_complete":
            newStatuses[event.agent_name] = "done";
            break;
          case "agent_failed":
            newStatuses[event.agent_name] = "error";
            break;
        }
      }

      return {
        isRunning: event.type !== "pipeline_complete",
        pipelineMode: event.pipeline_mode,
        pipelineRunId: event.pipeline_run_id,
        agentStatuses: newStatuses,
        events: [...state.events.slice(-99), event],
      };
    }),

  clearEvents: () => set({ events: [], agentStatuses: {} }),
}));
