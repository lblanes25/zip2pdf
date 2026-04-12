# Prompt: Edge Derivation — Build Master Edge List (Production Run)

I've uploaded the Layer 1 output workbook from the prior step. I need you to derive entity-to-entity edges from the shared attribute tables and combine them with the handoff edges into a master edge list.

---

## Step 1: Derive Shared-Attribute Edges

For each shared-attribute table (Entity-Application, Entity-Vendor, Entity-Model, Entity-PRSA), find all pairs of entities that share the same value.

Rules:
- Each pair appears once per shared value (A-B, not both A-B and B-A)
- If Entity A and Entity B share 3 applications, that's 3 rows (one per shared app)
- Flag shared values with 10+ dependent entities as "high frequency" — still include the edges but flag them for density management

Output columns:
- Entity A ID
- Entity B ID
- Edge Type (shared_app / shared_vendor / shared_model / shared_prsa)
- Shared Value (the specific asset name)
- High Frequency Flag (TRUE if the shared value has 10+ dependent entities)

---

## Step 2: Build Master Edge List

Combine handoff edges (from the Handoffs sheet) with the shared-attribute edges into a single master edge list:
- Entity A ID
- Entity B ID
- Edge Type (handoff_to / handoff_from / shared_app / shared_vendor / shared_model / shared_prsa)
- Detail (shared value name for shared attributes, blank for handoffs)
- High Frequency Flag

---

## Step 3: Summary Statistics

**Overall:**
- Total edges in master list
- Total edges by type
- Unique entity pairs with at least one edge
- Entity pairs connected by multiple edge types (count)
- Isolated entities (zero edges — list them)

**Connectivity:**
- Top 15 most connected entities (all edges) — Entity ID, Name, edge count
- Top 10 most connected entities (handoffs only)
- Bottom 10 non-isolated entities (fewest connections)

**Shared Assets:**
- Top 10 most shared applications (by entity count)
- Top 10 most shared vendors
- Top 10 most shared models
- Top 10 most shared PRSAs

**High Frequency Values:**
- List all shared values with 10+ dependent entities
- For each: value name, asset type, entity count, total edges generated

**Risk Overlay (from Risk Map sheet):**
- For each of the 14 risks: entity count carrying that risk, average connection count of those entities
- Which risk has the most interconnected entity set?
- Which risk has the least?

---

## Output

Provide as separate sheets in a single Excel workbook:
1. Master Edge List
2. High Frequency Shared Values
3. Summary Statistics
