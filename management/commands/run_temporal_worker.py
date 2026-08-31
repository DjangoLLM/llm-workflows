import asyncio
import concurrent.futures
import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from temporalio.client import Client
from temporalio.worker import Worker

from agents.core.temporal.worker_plugins import build_temporal_worker_composition

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Runs the Temporal worker for processing agent pipelines."

    def handle(self, *args, **options):
        try:
            asyncio.run(self.run_worker())
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS("Worker stopped manually."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Worker failed: {e}"))
            raise e

    async def run_worker(self):
        # Default fallback to localhost if not set, though settings.py usually has it.
        server_url = getattr(settings, "TEMPORAL_SERVER_URL", "localhost:7233")
        task_queue = getattr(settings, "TEMPORAL_TASK_QUEUE", "ai-pipeline-queue")
        worker_composition = build_temporal_worker_composition()

        self.stdout.write(f"Connecting to Temporal server at {server_url}...")
        client = await Client.connect(server_url)

        plugin_modules_label = ", ".join(worker_composition.plugin_modules)
        self.stdout.write(f"Loaded Temporal plugin modules: {plugin_modules_label}")
        self.stdout.write(
            "Registered "
            f"{len(worker_composition.workflows)} workflows and "
            f"{len(worker_composition.activities)} activities."
        )
        logger.info(
            "Temporal worker plugin load complete",
            extra={
                "plugin_modules": worker_composition.plugin_modules,
                "plugin_slugs": worker_composition.plugin_slugs,
                "workflow_count": len(worker_composition.workflows),
                "activity_count": len(worker_composition.activities),
            },
        )

        self.stdout.write(f"Starting worker on queue '{task_queue}'...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as activity_executor:
            worker = Worker(
                client,
                task_queue=task_queue,
                workflows=worker_composition.workflows,
                activities=worker_composition.activities,
                activity_executor=activity_executor,
            )

            self.stdout.write(self.style.SUCCESS("Worker is running. Press Ctrl+C to cancel."))
            await worker.run()
