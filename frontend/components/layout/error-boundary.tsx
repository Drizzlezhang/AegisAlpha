"use client";

import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          className="flex flex-col items-center justify-center p-8 gap-4"
          style={{ background: "var(--aegis-bg-base)" }}
        >
          <h2
            className="text-lg font-semibold"
            style={{ color: "var(--aegis-signal-bear)" }}
          >
            Something went wrong
          </h2>
          <p
            className="text-sm"
            style={{ color: "var(--aegis-text-secondary)" }}
          >
            {this.state.error?.message || "An unexpected error occurred"}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: undefined })}
            className="px-4 py-2 text-sm rounded-md transition-colors duration-150"
            style={{
              background: "var(--aegis-brand)",
              color: "var(--aegis-text-primary)",
            }}
          >
            Try Again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
