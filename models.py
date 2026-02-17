import uuid

from django.db import models
from django.utils import timezone


class AgentRunStatus(models.TextChoices):
    """Lifecycle states for AgentRun rows."""

    PENDING = "PENDING", "Pending"
    RUNNING = "RUNNING", "Running"
    SUCCEEDED = "SUCCEEDED", "Succeeded"
    FAILED = "FAILED", "Failed"


class AgentRun(models.Model):
    """Persist each agent execution attempt."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent_label = models.CharField(max_length=120)
    status = models.CharField(
        max_length=16,
        choices=AgentRunStatus.choices,
        default=AgentRunStatus.PENDING,
    )
    input = models.JSONField(null=True, blank=True)
    output = models.JSONField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class PipelineStatus(models.TextChoices):
    """Lifecycle states for pipeline runs and steps."""

    PENDING = "PENDING", "Pending"
    RUNNING = "RUNNING", "Running"
    SUCCEEDED = "SUCCEEDED", "Succeeded"
    FAILED = "FAILED", "Failed"


class PipelineRun(models.Model):
    """Track a multi-step pipeline execution."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pipeline_name = models.CharField(max_length=128)
    status = models.CharField(
        max_length=16,
        choices=PipelineStatus.choices,
        default=PipelineStatus.PENDING,
    )
    current_step = models.CharField(max_length=128, null=True, blank=True)
    context = models.JSONField(null=True, blank=True)
    root_payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def create_run(cls, pipeline_name: str, root_payload: dict | None = None, context: dict | None = None):
        # Create run with initial payload and context snapshot.
        """Factory for a new pipeline run with initial payload/context."""
        return cls.objects.create(
            pipeline_name=pipeline_name,
            status=PipelineStatus.PENDING,
            current_step=None,
            context=context or {},
            root_payload=root_payload,
        )

    def set_running(self, current_step: str) -> None:
        # Mark run active and note current step name.
        """Mark run as running and set current step."""
        self.status = PipelineStatus.RUNNING
        self.current_step = current_step
        self.save(update_fields=["status", "current_step", "updated_at"])

    def mark_failed(self, current_step: str | None = None) -> None:
        # Mark run failed and persist latest step pointer.
        """Mark run failed and optionally set current step."""
        self.status = PipelineStatus.FAILED
        if current_step:
            self.current_step = current_step
        self.save(update_fields=["status", "current_step", "updated_at"])

    def mark_succeeded(self) -> None:
        # Mark run success and clear current step.
        """Mark run succeeded and clear current step."""
        self.status = PipelineStatus.SUCCEEDED
        self.current_step = None
        self.save(update_fields=["status", "current_step", "updated_at"])

    def update_context(self, context: dict) -> None:
        # Persist shared context changes.
        """Persist updated shared context."""
        self.context = context
        self.save(update_fields=["context", "updated_at"])


class PipelineStep(models.Model):
    """Track an individual step within a pipeline run."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        PipelineRun,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    agent_run = models.ForeignKey(
        "AgentRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pipeline_steps",
    )
    step_name = models.CharField(max_length=128)
    order_index = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        choices=PipelineStatus.choices,
        default=PipelineStatus.PENDING,
    )
    input_payload = models.JSONField(null=True, blank=True)
    output_payload = models.JSONField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    parents = models.ManyToManyField("self", symmetrical=False, related_name="children", blank=True)

    class Meta:
        index_together = [
            ("run", "order_index"),
            ("run", "step_name"),
        ]

    @classmethod
    def create_step(
        cls,
        run: PipelineRun,
        step_name: str,
        order_index: int,
        input_payload: dict | None = None,
        agent_run: "AgentRun | None" = None,
    ):
        # Create a new step row for the run.
        """Factory for a new pipeline step."""
        return cls.objects.create(
            run=run,
            agent_run=agent_run,
            step_name=step_name,
            order_index=order_index,
            status=PipelineStatus.PENDING,
            input_payload=input_payload,
        )

    def mark_running(self) -> None:
        # Mark step active with start time.
        """Mark step as running."""
        self.status = PipelineStatus.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at", "updated_at"])

    def mark_finished(self, status: str, output_payload: dict | None = None, error: str | None = None) -> None:
        # Mark step terminal with output or error.
        """Mark step finished with result or error."""
        self.status = status
        self.output_payload = output_payload
        self.error_message = error
        self.ended_at = timezone.now()
        self.save(
            update_fields=[
                "status",
                "output_payload",
                "error_message",
                "ended_at",
                "updated_at",
            ]
        )
