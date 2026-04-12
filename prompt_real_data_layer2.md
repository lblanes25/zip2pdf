# Prompt: Layer 2 — Coverage Matrix & Gap Analysis (Production Run)

I've uploaded three files:
1. The Layer 1 output workbook (14 sheets of parsed audit universe data)
2. The Edge Derivation output workbook (Master Edge List, High Frequency Shared Values, Summary Statistics)
3. A list of Entity IDs that are in-scope for the current audit cycle

I need you to build a coverage matrix that answers three questions:
- Where are the coverage gaps when we account for how entities connect?
- Where does concentration risk create uncovered exposure?
- Where does an entity's connectivity suggest its audit frequency should be reconsidered?

**CRITICAL: Exclude shared_model edges from all connectivity counts and coverage flags.** Models are too dense — a small group of model-heavy entities shares many models, generating ~9,900 edges that distort the network. Models are analyzed separately as concentration risk (Step 4), not as pairwise connections. Only use these edge types for connectivity: handoff_to, handoff_from, shared_app, shared_vendor, shared_prsa.

---

## Step 1: Build the Coverage Matrix

For each entity in the Nodes table, create one row with:

**Identity:**
- Entity ID
- Entity Name
- Business Unit
- Horizontal Flag

**Audit Status:**
- In Scope This Year (Yes/No — match against the uploaded audit plan list)
- Effective Audit Frequency (from Audit Cycle Summary sheet)
- Last Audit Date
- Days Since Last Audit
- Overdue (Yes/No)

**Connection Counts (unweighted, by type — from Master Edge List, excluding shared_model):**
- Handoff-to count
- Handoff-from count
- Shared application count
- Shared vendor count
- Shared PRSA count
- **Connectivity Total** (sum of above — this drives all coverage flags)

**Model Exposure (informational, not included in connectivity total):**
- Model count (from Entity-Model table in Layer 1 workbook — number of models this entity uses, NOT pairwise edges)

**Risk Profile:**
- Count of risks rated High or Critical (residual)
- Count of risks rated Insufficiently or Partially Controlled
- Count of risks that are BOTH High/Critical residual AND weak controls
- Highest individual residual risk rating across all 14 risks
- List of risks rated High or Critical (names)

Sort by Connectivity Total descending.

---

## Step 2: Coverage Flags

Generate flags for the following conditions. Each flag should include: Flag Type, Entity ID, Entity Name, Detail (human-readable explanation), Priority (HIGH / MEDIUM / LOW).

### Flag 1: COVERAGE GAP — CONNECTED CLUSTER (HIGH)
Find groups of 5+ entities connected by handoffs where NONE are in the current audit plan. List the group, their handoff connections, and their risk profiles.

### Flag 2: OVERDUE + HIGHLY CONNECTED (HIGH)
Entities that are overdue AND in the top quartile of Connectivity Total (excluding models). These are the highest priority gaps — entities at the center of the network that haven't been audited within their required frequency.

### Flag 3: CONCENTRATION ASSET — ZERO COVERAGE (HIGH)
Vendors, applications, or **models** with 10+ dependent entities where NO dependent entity is in the current audit plan. Include: asset name, asset type, dependent entity count, and dependent entity IDs. Models are especially important here — they were excluded from connectivity counts because of density, but concentration risk on specific models is still a real exposure.

### Flag 4: PRIMARY CONTROL OWNER NOT IN PLAN (HIGH)
For concentration assets (10+ dependent entities), check whether the primary entity (the one that owns/tests the controls) is in the audit plan. If not, flag it — secondary entities are relying on controls nobody is verifying this cycle.

### Flag 5: CONNECTIVITY SUGGESTS HIGHER FREQUENCY (MEDIUM)
Entities where:
- Their overall residual risk rating is Low or Medium (driving a 3-4 year cycle)
- BUT they hand off to multiple entities rated High or Critical
- OR they are the primary control owner for a concentration asset
These entities may be more important than their standalone rating suggests.

### Flag 6: HIGH RISK + WEAK CONTROLS, NOT IN PLAN (MEDIUM)
Entities with at least one risk rated High/Critical residual AND Insufficiently/Partially Controlled, that are not in the current plan.

### Flag 7: FREQUENCY OVERRIDE ON CONNECTED ENTITY (LOW)
Entities whose audit frequency was overridden AND that are in the top quartile of Connectivity Total (excluding models). These overrides may not have accounted for connectivity.

---

## Step 3: Coverage Summary

Provide a summary table with:

**Overall:**
- Total active entities
- In scope this year (count and %)
- Overdue entities (count)
- Overdue and not in plan (count)

**Connectivity-Adjusted (excluding model edges):**
- Top 20 most connected entities by Connectivity Total: how many are in scope?
- Top 10 most connected entities by Connectivity Total: how many are in scope?
- Horizontal (cross-cutting) entities: how many are in scope?

**Concentration (including models):**
- Total concentration assets (10+ dependent entities)
- Concentration assets with zero audit coverage
- Concentration assets where primary control owner is not in plan

**Risk:**
- Entities with High/Critical residual + weak controls: total count, count not in plan
- Average Connectivity Total of High/Critical risk entities vs. Low risk entities

**Flags:**
- Total flags generated by type and priority

---

## Step 4: Concentration Risk Detail

For each concentration asset (10+ dependent entities) — **including models, vendors, and applications** — provide:
- Asset Name
- Asset Type
- Dependent entity count
- Primary entity (which entity owns controls) — is it in the plan?
- Secondary entities — how many are in the plan?
- Business units affected
- Coverage rate (% of dependent entities in plan)

Sort by coverage rate ascending (least covered first).

---

## Output

Provide all tables as separate sheets in a single Excel workbook:
1. Coverage Matrix
2. Coverage Flags (color-coded: red = HIGH, yellow = MEDIUM, gray = LOW)
3. Coverage Summary
4. Concentration Risk Detail
