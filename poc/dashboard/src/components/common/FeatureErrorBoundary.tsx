import React from 'react';

interface FeatureErrorBoundaryProps {
  children: React.ReactNode;
  fallback: React.ReactNode;
}

/** Contains render/lazy-import failures within one optional feature subtree. */
export class FeatureErrorBoundary extends React.Component<
  FeatureErrorBoundaryProps,
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    console.error('Optional feature failed to render', error, info.componentStack);
  }

  render(): React.ReactNode {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}
