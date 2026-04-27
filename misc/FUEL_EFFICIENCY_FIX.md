# Fuel Efficiency Calculation

## Algorithm

The fuel efficiency is calculated using a simple, straightforward approach:

```python
For each vehicle:
    1. Distance = sum of (end odo - start odo) for each trip
    2. Liters = sum of all refill liters
    3. Vehicle KM/L = Distance / Liters

Overall = Weighted average by distance
```

## Key Points

1. **Distance**: Calculated from "start odo" → "end odo" pairs
   - When you see "start odo", record the ODO
   - When you see "end odo", calculate: distance = end_odo - start_odo
   - Sum all distances

2. **Liters**: Sum of all "refill odo" liters
   - **Do NOT use the ODO reading from refill events**
   - Only sum the liters from all refill events

3. **Validation**: Both distance and liters must be > 0

## Example Calculation

**Vehicle AAN1529:**
- Trip: start odo 5000 → end odo 5550 = 550 KM
- Refills: 100L + 100L = 200 L
- Vehicle KM/L: 550 / 200 = 2.75

**Vehicle ABD7315:**
- Trip: start odo 6000 → end odo 6250 = 250 KM
- Refills: 63L + 300L = 363 L
- Vehicle KM/L: 250 / 363 = 0.69

**Overall:**
- Total distance: 550 + 250 = 800 KM
- Total liters: 200 + 363 = 563 L
- Weighted KM/L: (2.75 × 550 + 0.69 × 250) / 800 = **2.1 KM/L**

## ODO Workflow

- **"start odo"** - Starting ODO for the day's trip
- **"end odo"** - Ending ODO for the day's trip
- **"refill odo"** - Fuel refill event (record liters, ignore ODO value)

## Notes

- The ODO reading at refill time is **NOT** used for distance calculation
- Multiple refills are summed independently
- The algorithm handles partial data (vehicles without trips or refills are skipped)
