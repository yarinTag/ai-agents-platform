# Dashboard React hooks

This directory owns reusable React state/lifecycle hooks. Feature-specific hooks remain beside their owning pages or components; avoid importing page implementations into reusable hooks. Keep source files at most 500 physical lines.

## Obsolete request containment

useRequestGeneration provides stable begin/invalidate functions. A request generation remains current only while mounted and while no later request/context invalidation has superseded it. MCP and Calendar loading callbacks use it to ignore stale responses after refresh, context change or unmount. It performs no HTTP calls and does not replace server authorization. No build or runtime checks were run.

Update this guide whenever reusable hook behavior changes. Existing useOfficeEvents remains the live Office/task event integration; its existing public behavior was not rewritten by the request-generation addition.
