# Prompt: Full Audit Universe Network Visualization — 427 Entities by Business Unit

Using the data already loaded in this conversation (Coverage Matrix, Nodes, Handoffs from Layer 1, and Master Edge List), generate an interactive HTML network graph showing all 427 active entities.

## Important: Density Management

427 entities with 7,000+ edges will be unreadable without aggressive filtering. Apply these rules:

**Default view shows only handoff edges.** These are the strongest operational connections and the most readable. Shared apps, vendors, and PRSAs should be toggle-able layers that the user can turn on/off, but they start OFF.

**Only show edges between entities within the same business unit OR handoff edges that cross business units.** This keeps clusters clean. Cross-unit handoffs are the most interesting — they show where risk flows between organizational boundaries.

## Layout: Grouped by Business Unit

- Arrange entities into **visual clusters by Business Unit** — entities in the same BU should be grouped together in a distinct region of the graph
- Draw a light background box, shaded region, or convex hull around each BU cluster with the BU name as a label
- Within each cluster, use force-directed layout so connected entities pull together
- Leave clear spacing between BU clusters so they're visually distinct
- Cross-BU edges should be clearly visible as lines that span between clusters

## Node Design

- **Size:** Proportional to Connectivity Total. Minimum size for readability, maximum capped so large nodes don't overwhelm.
- **Color by coverage status:**
  - Green (#27ae60) = In Scope This Year
  - Red (#c0392b) = Not In Scope, Not Overdue
  - Dark Red / Bright Red (#e74c3c) with border = Not In Scope AND Overdue
  - Light Green (#a9dfbf) = In Scope AND Overdue (covered but late)
- **Shape:** Diamond for horizontal (cross-cutting) entities, circle for vertical
- **Labels:** Show Entity ID only at default zoom. Show full Entity Name on hover or when zoomed in. At full zoom-out, hide labels entirely to keep it clean.
- **Hover tooltip:** Entity ID, full Entity Name, Business Unit, Connectivity Total, Overall Residual Risk Rating, In Scope (Yes/No), Overdue (Yes/No), Handoff-to count, Handoff-from count, High/Critical risks list

## Edge Design

- **Handoff edges (default ON):** Solid lines, medium gray (#666), thickness proportional to whether it's one-directional or bidirectional (thicker = both to and from exist between the pair)
- **Shared app edges (toggle, default OFF):** Thin lines, light blue (#3498db), 50% opacity
- **Shared vendor edges (toggle, default OFF):** Thin lines, orange (#e67e22), 50% opacity
- **Shared PRSA edges (toggle, default OFF):** Thin dotted lines, light purple (#9b59b6), 30% opacity
- **Never show shared_model edges**

## Interactive Controls

Include a control panel (sidebar or top bar) with:
- **Edge type toggles:** Checkboxes for Handoffs (default ON), Shared Apps, Shared Vendors, Shared PRSAs
- **Filter by Business Unit:** Dropdown or checkboxes to show/hide specific BU clusters
- **Filter by coverage status:** Buttons for "All", "Not In Scope Only", "Overdue Only"
- **Search:** Text box to find an entity by name or ID — highlights the entity and its immediate connections
- **Reset view** button

## Legend

- Node colors (In Scope / Not In Scope / Overdue combinations)
- Node shapes (Horizontal / Vertical)
- Edge types with their visual styles
- Node size = Connectivity Total

## Title

"Audit Universe Network — 427 Entities Grouped by Business Unit"

Subtitle: "Default view: handoff edges only. Toggle shared assets in the control panel. Node size = connectivity. Color = audit plan coverage."

## Output

Save as a single self-contained HTML file. Use D3.js (preferred for this complexity) or Plotly. Must be interactive — zoom, pan, hover, filter. Should load and perform reasonably in a modern browser.

## Performance Notes

- 427 nodes is manageable but 7,000+ edges is not — this is why edge toggles default to handoffs-only (~4,500 edges, which is still dense). If performance is an issue, consider only drawing edges for visible/filtered nodes.
- Consider using canvas rendering instead of SVG if D3, for better performance with this many elements.
- Cluster layout can be pre-computed (run force simulation for each BU separately, then position BU clusters on a larger grid) rather than simulating all 427 nodes at once.
