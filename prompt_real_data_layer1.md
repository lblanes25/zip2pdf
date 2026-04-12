# Prompt: Layer 1 — Parse Audit Universe (Production Run)

I've uploaded a CSV of our audit universe from Archer — one row per auditable entity, approximately 401 rows and 70 columns. I need you to parse it into clean relational tables that will serve as the data foundation for audit planning analysis.

This is production data. Be precise. Document every decision.

---

## Filtering

Before starting, remove:
- Entities where Audit Entity Type indicates a special/one-time review (not a standard recurring audit entity)
- Entities where Audit Entity Status is not Active

Report:
- How many entities were removed by each filter
- How many remain
- List the Entity IDs removed (so I can verify)

---

## Step 1: Node Table

Create a table called **Nodes** — one row per remaining entity:
- Audit Entity ID
- Audit Entity Name
- Business Unit
- Line of Defense
- Subsidiary Bank
- Core Audit Team
- Integrated Team
- Audit Leader
- PGA/ASL
- Horizontal Flag — mark as "horizontal" if the entity name indicates a cross-cutting function (e.g., AML, KYC, Sanctions, Compliance, IT, Cybersecurity, Data Governance, Vendor Management, Model Validation, Internal Controls, Business Continuity, Fraud, Operational Risk, Market Risk, Credit Risk). Otherwise "vertical."

---

## Step 2: Risk Map

Create a table called **Risk Map** — one row per entity-risk combination where the risk is applicable.

The CSV contains 14 risks, each with 3 columns: Inherent Risk Rating, Residual Risk Rating, and Control Assessment Rating. Identify these triplets from the column headers.

For each entity-risk combination, include a row if the Residual Risk Rating is NOT "Not Applicable" and NOT blank:
- Entity ID
- Risk Name (e.g., "Compliance", "Credit", "Third Party")
- Inherent Risk Rating
- Residual Risk Rating (this is the operative rating — drives audit frequency)
- Control Assessment Rating

---

## Step 3: Relational Tables

Split multi-value cells (semicolon-delimited) and create one table per relationship type.

**CRITICAL: Standardization.** If the same value appears with different spellings, capitalization, whitespace, or formatting across rows or columns — unify them. Log every standardization decision in a separate table showing: original value, standardized value, which table, and how many rows were affected.

### 3a. Handoffs
- Source Entity ID
- Target Entity ID
- Direction: "to" or "from"
- Unmatched Flag: TRUE if the target/source ID does not exist in the Nodes table

### 3b. Entity-Application
- Entity ID
- Application Name
- Relationship: "primary" (from PRIMARY IT APPLICATIONS column) or "secondary" (from SECONDARY IT APPLICATIONS column)
- Primary = entity owns/tests the application controls
- Secondary = entity's key controls depend on this application without owning control testing
- Standardize application names ACROSS both primary and secondary columns

### 3c. Entity-Vendor
- Entity ID
- Third Party Name
- Relationship: "primary" or "secondary" (same logic as applications)
- Standardize vendor names across both columns

### 3d. Entity-Model
- Entity ID
- Model Name

### 3e. Entity-PRSA
- Entity ID
- PRSA Value
- PRSA is a confirmed edge type for this project

### 3f. Entity-Policy (Exploratory)
- Entity ID
- Policy/Standard ID or Name
- Normalize ID formats (spaces vs. underscores)
- This is exploratory — I need to see the distribution before deciding whether to use it

---

## Step 4: Dependency Lookups

### 4a. Asset Dependency Lookup
For each unique application, vendor, and model:
- Asset Name
- Asset Type (application / vendor / model)
- Count of dependent entities
- List of dependent Entity IDs
- Business units represented
- Primary count (how many entities list it as primary)
- Secondary count (how many list it as secondary)

Sort by count descending within each asset type.

### 4b. Entity Dependency Profile
For each entity:
- Entity ID
- Entity Name
- Handoff-to count
- Handoff-from count
- Primary application count
- Secondary application count
- Primary vendor count
- Secondary vendor count
- Model count
- PRSA count
- Total connection count (simple sum, no weighting)
- Handoff partner Entity IDs

Sort by total connection count descending.

### 4c. Concentration Flags
Flag any asset (application, vendor, or model) with 10+ dependent entities:
- Asset Name
- Asset Type
- Count of dependent entities
- Primary entity count / Secondary entity count
- Dependent Entity IDs
- Business units affected

---

## Step 5: PRSA & Policy Distribution Analysis

**For PRSA:**
- For each unique PRSA value: entity count, potential edges (n*(n-1)/2), entity IDs
- Distribution: how many values have 1-5 entities? 6-15? 16-50? 50+?
- Total potential edges

**For Policies:**
- Same breakdown
- Total potential edges
- Recommendation: given the distribution, should any subset be used as edges?

---

## Step 6: Audit Cycle Summary

For each entity, compute:
- Effective audit frequency (use override value if override = Yes, otherwise use calculated minimum)
- Last audit date
- Days since last audit
- Whether the entity appears overdue based on frequency vs. last audit date

Provide as a table sorted by days since last audit (descending).

---

## Step 7: Validation

Report:
- Row counts for every table created
- All unmatched handoff references (list every AE ID that appears in handoffs but not in Nodes)
- Per relational table: count of unique values and top 10 most common values
- Entities with zero connections of any type (list them)
- Full standardization log
- Any data quality issues or anomalies encountered during parsing

---

## Output

Provide all tables as separate sheets in a single Excel workbook:
1. Nodes
2. Risk Map
3. Handoffs
4. Entity-Application
5. Entity-Vendor
6. Entity-Model
7. Entity-PRSA
8. Entity-Policy (Exploratory)
9. Asset Dependency Lookup
10. Entity Dependency Profile
11. Concentration Flags
12. PRSA & Policy Distribution
13. Audit Cycle Summary
14. Validation & Standardization Log
