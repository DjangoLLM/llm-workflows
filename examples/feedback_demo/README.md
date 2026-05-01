# Feedback Pipeline Demo

This is a throw-away Django project that demonstrates the README feedback
pipeline with Temporal and the reusable `agents` app.

## Run

```bash
cp examples/feedback_demo/.env.example examples/feedback_demo/.env
# Edit examples/feedback_demo/.env and set OPENAI_API_KEY.
docker compose -f examples/feedback_demo/docker-compose.yml up --build
```

Open:

- Django demo UI: http://localhost:8000
- Temporal UI: http://localhost:8233

The page submits feedback, starts `feedback.pipeline.workflow`, polls the
`PipelineRun` ledger, and displays the final LLM analysis when the workflow
finishes.
