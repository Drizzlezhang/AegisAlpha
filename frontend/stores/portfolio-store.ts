import { create } from "zustand";
import type {
  PortfolioSnapshot,
  Position,
  GreeksSummary,
  HealthScore,
} from "@/lib/types";

interface PortfolioStore {
  snapshot: PortfolioSnapshot | null;
  positions: Position[];
  greeks: GreeksSummary | null;
  healthScores: HealthScore[];

  setSnapshot: (data: PortfolioSnapshot) => void;
  setPositions: (data: Position[]) => void;
  setGreeks: (data: GreeksSummary) => void;
  setHealthScores: (data: HealthScore[]) => void;
}

export const usePortfolioStore = create<PortfolioStore>((set) => ({
  snapshot: null,
  positions: [],
  greeks: null,
  healthScores: [],

  setSnapshot: (data) => set({ snapshot: data }),
  setPositions: (data) => set({ positions: data }),
  setGreeks: (data) => set({ greeks: data }),
  setHealthScores: (data) => set({ healthScores: data }),
}));
