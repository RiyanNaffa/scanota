# Evolus Integration – scanota

## Building Blocks Used

1. **Document Extractor** – extracts structured data from receipt images
2. **Workflow** – triggered for flagged (needs_review) transactions
3. *(Optional)* **AI Tool** – for additional text processing
4. *(Optional)* **Knowledge Library** – for product/SKU enrichment

## What to Create in Evolus Workspace

1. Create a Document Extractor trained on Indonesian receipt images
2. Create a Workflow that handles flagged receipt notifications
3. Note your `workspace_id`, extractor ID, and workflow ID

## How to Configure

1. Edit `evolus/endpoints.yaml` — replace all `TO_CONFIRM` values with actual paths
2. Set env vars in `.env`:
   ```
   EVOLUS_BASE_URL=https://api.evolus.ai
   EVOLUS_API_KEY=your-key-here
   EVOLUS_WORKSPACE_ID=your-workspace-id
   EVOLUS_ENABLED=true
   EXTRACTION_BACKEND=evolus
   ```
3. Test with `curl localhost:8000/evolus/stats`

## UNVERIFIED Items

- Actual Evolus REST API paths (marked `TO_CONFIRM` in `endpoints.yaml`)
- Evolus extractor response schema (mapper in `app/evolus/mapper.py` uses placeholder field names)
- Live workspace integration test

## Code Locations

- Client: `app/evolus/client.py`
- Response mapper: `app/evolus/mapper.py`
- Endpoint config: `evolus/endpoints.yaml`
- Stats endpoint: `GET /evolus/stats`
