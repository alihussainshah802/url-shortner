import { Component, type ErrorInfo, type ReactNode } from "react";

import { Button } from "@/components/ui/button.tsx";

interface State {
  failed: boolean;
}

/** Catches a crash while rendering and shows a recovery screen instead of a blank page. */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled UI error", error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;

    return (
      <div className="mx-auto flex min-h-screen w-full max-w-xl flex-col justify-center px-4">
        <div
          role="alert"
          className="rounded-lg bg-primary px-6 py-6 text-primary-foreground"
        >
          <p className="font-mono text-xs tracking-widest uppercase">Paper jam</p>
          <h1 className="mt-2 text-2xl leading-tight font-extrabold [font-stretch:125%]">
            Something broke on this page.
          </h1>
          <p className="mt-3 text-sm text-primary-foreground/80">
            Your links are safe. Reload the page to start again.
          </p>
          <Button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-5 h-11 bg-accent px-5 text-accent-foreground hover:bg-accent/85"
          >
            Reload page
          </Button>
        </div>
      </div>
    );
  }
}
