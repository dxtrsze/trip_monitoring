- when using "python app.py" command, use "uv run app.py" instead.
- when using "pip install <package>" command, use "uv add <package>" instead.
- when creating or adding new columns to the database, update "migrate_taiwan.py" to include the migration script.

## AI Scheduling Assistant

The AI Scheduling Assistant is an admin-only feature that enables natural language trip scheduling using an OpenAI-compatible LLM (Z.AI).

### Access

- URL: `/ai`
- Requires: Admin position
- Configuration: `ZAI_API_KEY` environment variable must be set

### Usage

1. **Set up API key:**
   ```bash
   # In .env file
   ZAI_API_KEY=your_actual_api_key_here
   ZAI_API_BASE=https://api.z.ai/api/paas/v4
   ZAI_MODEL=gpt-4
   ```

2. **Restart the application** to load environment variables

3. **Navigate to** `/ai` in your browser

4. **Type natural language commands:**
   - "Schedule ABC123 for North area on 2026-03-26"
   - "What vehicles are available?"
   - "Show me pending deliveries for South area on March 27"

5. **Review proposals** and click "Approve" to create schedules

### Supported Commands

- **Schedule creation:** "Schedule [plate_number] for [area] area on [date]"
- **Query vehicles:** "What vehicles are available?"
- **Query pending deliveries:** "Show pending deliveries for [area] on [date]"
- **Query drivers:** "What drivers are available?"

### How It Works

1. AI parses your natural language command
2. Queries database for matching vehicles, Data items, drivers
3. Groups Data by branch and calculates CBM
4. Presents proposal with trip details
5. Requires your approval before creating database records
6. Creates Schedule, Trip, TripDetail records
7. Updates Data.status to "Scheduled"

### Troubleshooting

- **"ZAI_API_KEY not configured"**: Set the environment variable in `.env` and restart
- **"No unscheduled deliveries found"**: Check Data.status is "Not Scheduled" and due_date matches
- **"Capacity exceeded"**: Total CBM exceeds vehicle capacity, consider using larger vehicle or splitting trips
- **"No available drivers"**: All drivers are already assigned to trips on that date

### Security

- Admin-only access enforced
- All write operations require explicit approval
- API key never logged or exposed in error messages
- SQL injection prevented via SQLAlchemy ORM
- Prompt injection protection via system prompt isolation