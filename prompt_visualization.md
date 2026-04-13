# Prompt: Focused Network Visualization — Top 30 Most Connected Entities

Using the data already loaded in this conversation (Coverage Matrix, Handoffs sheet from Layer 1, and Master Edge List), generate an interactive HTML network graph.

## Scope

Only include the **top 30 entities by Connectivity Total** (excluding shared_model edges, as already established). Include all edges between these 30 entities — handoffs, shared apps, shared vendors, and shared PRSAs. Do NOT include edges to entities outside the top 30.

## Node Design

- **Size:** Proportional to Connectivity Total. Biggest nodes = most connected.
- **Color by coverage status:**
  - Green (#27ae60) = In Scope This Year
  - Red (#e74c3c) = Not In Scope This Year
  - Orange (#f39c12) = Overdue (regardless of in-scope status)
- **Shape:** Diamond for horizontal (cross-cutting) entities, circle for vertical
- **Label:** Entity Name (short enough to read — truncate at ~25 characters if needed)
- **Hover tooltip:** Entity ID, full Entity Name, Connectivity Total, Overall Residual Risk Rating, In Scope (Yes/No), Overdue (Yes/No), list of High/Critical risks

## Edge Design

- Show edges between the top 30 entities only
- Use different styles for edge types:
  - Handoffs: solid lines, slightly thicker, dark gray
  - Shared apps: thin dashed lines, light blue
  - Shared vendors: thin dashed lines, orange
  - Shared PRSAs: thin dotted lines, light gray
- If two entities have multiple edge types, show only the strongest (handoff > app > vendor > prsa) to avoid visual clutter
- Do NOT show shared_model edges

## Layout

- Use a force-directed layout
- Entities with more connections to each other should cluster together naturally

## Legend

Include a legend showing:
- Node colors (In Scope / Not In Scope / Overdue)
- Node shapes (Horizontal / Vertical)
- Edge styles (Handoff / Shared App / Shared Vendor / Shared PRSA)

## Title

"Audit Universe — Top 30 Most Connected Entities by Audit Plan Coverage"

## Output

Save as a single self-contained HTML file with Plotly or D3 embedded. It should open in any browser with full interactivity — hover, zoom, pan.
