# Cluster-Based Scheduling Suggestions Design

## Summary

Add a smart scheduling suggestion feature to the existing `/ai` page that groups unscheduled deliveries by cluster area based on due date. Users see cluster cards with CBM/item totals, then select vehicle and driver via a modal to create schedules. No LLM call needed for suggestions — pure Python for speed and reliability.

## Context

- Existing `/ai` page has an AI scheduling assistant using a local LLM (Qwen3.5-9B-MLX-4bit via OpenAI-compatible API)
- Current flow: user types a command like "Schedule ABC123 for North area on 2026-03-26", LLM interprets, backend builds proposal
- New feature: user asks "What needs scheduling for March 28?", backend groups unscheduled items by cluster area, user picks vehicle/driver from modal

## Architecture

### Data Flow

1. User types a scheduling-related message (e.g., "What needs scheduling today?")
2. Backend detects intent via keyword matching (no LLM call)
3. Python runs `suggest_clusters(due_date)` to query and group data
4. Backend returns `type: "cluster_suggestions"` with structured cluster data
5. Frontend renders cluster cards with "Create Schedule" buttons
6. User clicks button, modal opens with vehicle/driver/assistant dropdowns
7. User submits, existing `execute_schedule()` creates the records

### Files Modified

- `ai_service.py` — add `suggest_clusters(due_date)` method
- `app.py` — add intent detection in `/api/ai/chat`, add `/api/ai/vehicles` and `/api/ai/drivers` endpoints
- `templates/ai.html` — add cluster card rendering, schedule creation modal, new quick action button

## Detailed Design

### 1. `suggest_clusters(due_date)` in `ai_service.py`

**Query:**
- `Data.status == "Not Scheduled"` AND `Data.due_date == due_date`
- LEFT JOIN `Cluster` on `func.lower(Cluster.branch) == func.lower(Data.branch_name_v2)`
- Branches without a cluster match go under area `"Unclustered"`

**Grouping:**
- Group by `Cluster.area`
- For each area: collect branches, sum CBM (`cbm * ordered_qty`), count items, collect data IDs

**Return structure:**
```python
{
    "type": "cluster_suggestions",
    "due_date": "2026-03-28",
    "total_unscheduled": 24,
    "clusters": [
        {
            "area": "North",
            "branches": ["B1", "B3", "B7"],
            "total_cbm": 5.2,
            "total_items": 12,
            "data_ids": [101, 102, 103],
        },
        ...
    ]
}
```

No vehicle or driver matching — user selects those when creating the schedule.

### 2. Intent Detection in `/api/ai/chat`

Keyword-based detection in the user message:

- **Trigger keywords:** "schedule", "scheduling", "suggest", "unscheduled", "what needs", "pending", "deliveries for", "today"
- **Date extraction:** Regex for `YYYY-MM-DD` format. Fallback to today's date if no date found
- **Fallback:** If no scheduling keywords match, route to existing LLM `chat()` method unchanged

### 3. New API Endpoints

#### `GET /api/ai/vehicles`
- Returns list of active vehicles (`status="Active"`, `dept="Logistics"`)
- Response: `[{"id": 1, "plate_number": "ABC123", "capacity": 10.0, "type": "in-house"}, ...]`

#### `GET /api/ai/drivers?date=YYYY-MM-DD`
- Returns available drivers not already assigned to trips on that date
- Checks `Trip` joined with `Schedule` where `delivery_schedule == date` for existing driver assignments
- Response: `[{"id": 2, "name": "Juan Dela Cruz", "role": "Driver"}, ...]`
- Same logic for assistants

### 4. Frontend Changes to `ai.html`

**Cluster card rendering:**
- When `data.type === "cluster_suggestions"`, render structured cards instead of plain text
- Each card shows: area name, branch list, total CBM, total items, "Create Schedule" button

**Schedule creation modal:**
- Triggered by clicking "Create Schedule" on a cluster card
- Fields:
  - Area and date (read-only, pre-filled from suggestion)
  - Vehicle dropdown (fetched from `/api/ai/vehicles`)
  - Driver dropdown (fetched from `/api/ai/drivers?date=...`)
  - Assistant dropdown (fetched from `/api/ai/drivers?date=...` with assistant role)
  - Submit button
- On submit: POST to `/api/ai/execute` with proposal constructed from selected values
- On success: show confirmation with link to `/schedules`

**New quick action button:**
- "What needs scheduling today?" — triggers the suggestion flow for today's date

### 5. Schedule Creation

Reuses existing `execute_schedule()` in `ai_service.py`. The frontend constructs the proposal object from the modal form values to match the expected format:

```json
{
  "proposal": {
    "delivery_schedule": "2026-03-28",
    "plate_number": "ABC123",
    "capacity": 10.0,
    "total_cbm": 5.2,
    "trips": [{
      "trip_number": 1,
      "vehicle_id": 5,
      "driver_ids": [2],
      "assistant_ids": [3],
      "details": [{
        "branch_name_v2": "B1",
        "data_ids": [101, 102],
        "total_cbm": 2.1,
        "total_ordered_qty": 5,
        "area": "North"
      }]
    }]
  }
}
```

No new backend logic for schedule creation.

## Access Control

- Admin-only access (matches existing `/ai` page — `current_user.position == "admin"`)
- All new endpoints inherit the same `@login_required` + admin check pattern

## Error Handling

- No unscheduled deliveries for date → return `type: "query"` with message "No unscheduled deliveries found for [date]"
- No vehicles available → disable vehicle dropdown, show warning
- No drivers available → disable driver dropdown, show warning
- API errors → standard error response format matching existing pattern

## Out of Scope

- LLM-generated natural language summaries of suggestions
- Automatic vehicle/driver assignment
- Multi-trip splitting for clusters exceeding vehicle capacity
- Editing existing schedules from this feature
