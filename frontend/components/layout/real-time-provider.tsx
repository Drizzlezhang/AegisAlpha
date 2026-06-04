"use client";

import { createContext, useContext, useEffect, type ReactNode } from "react";
import { wsClient } from "@/lib/ws";
import { usePipelineStore } from "@/stores/pipeline-store";

interface RealTimeContextValue {
  isConnected: boolean;
}

const RealTimeContext = createContext<RealTimeContextValue>({
  isConnected: false,
});

export function useRealTime() {
  return useContext(RealTimeContext);
}

export default function RealTimeProvider({ children }: { children: ReactNode }) {
  const handleEvent = usePipelineStore((s) => s.handleEvent);
  const connect = usePipelineStore((s) => s.connect);
  const disconnect = usePipelineStore((s) => s.disconnect);
  const isConnected = usePipelineStore((s) => s.isConnected);

  useEffect(() => {
    const unsub = wsClient.onEvent(handleEvent);

    // Connect if WebSocket is available
    if (process.env.NEXT_PUBLIC_WS_ENABLED !== "false") {
      wsClient.connect();
      connect();
    }

    return () => {
      unsub();
      wsClient.disconnect();
      disconnect();
    };
  }, [handleEvent, connect, disconnect]);

  return (
    <RealTimeContext.Provider value={{ isConnected }}>
      {children}
    </RealTimeContext.Provider>
  );
}
