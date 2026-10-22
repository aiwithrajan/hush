from datetime import timedelta
from typing import Dict, Any, Optional
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from hush.temporal.activities import (
        activity_ingest_notifications,
        activity_classify_pending,
        activity_generate_brief,
        activity_send_interrupt_alert,
        activity_check_acknowledgement,
        activity_send_escalation_alert,
        ClassificationItem,
        BriefSummary,
        IngestOutput,
        LOCAL_MODEL_RETRY_POLICY,
    )


TASK_QUEUE_NAME = "hush-attention-queue"


@workflow.defn
class HushInterruptEscalationWorkflow:
    """
    Durable Escalation Workflow enforcing the 'Never nag twice' rule:
    1. Fires initial alert.
    2. Waits for 10 minutes (or until acknowledgement signal).
    3. If unacknowledged after 10 minutes, escalates exactly ONCE.
    4. Never nags twice.
    """

    def __init__(self):
        self._acknowledged: bool = False
        self._escalated: bool = False
        self._verdict: Optional[str] = None
        self._interrupt_id: Optional[int] = None

    @workflow.signal
    def acknowledge(self, verdict: str = "useful"):
        """Signal delivered when user taps or acknowledges the notification."""
        self._acknowledged = True
        self._verdict = verdict

    @workflow.query
    def get_escalation_state(self) -> Dict[str, Any]:
        return {
            "interrupt_id": self._interrupt_id,
            "acknowledged": self._acknowledged,
            "escalated": self._escalated,
            "verdict": self._verdict,
        }

    @workflow.run
    async def run(self, item: ClassificationItem) -> Dict[str, Any]:
        # Step 1: Initial alert
        self._interrupt_id = await workflow.execute_activity(
            activity_send_interrupt_alert,
            item,
            start_to_close_timeout=timedelta(seconds=15),
        )

        # Step 2: Durable wait for 10 minutes (or until acknowledged via signal)
        try:
            await workflow.wait_condition(
                lambda: self._acknowledged,
                timeout=timedelta(minutes=10),
            )
        except Exception:
            pass

        # Also check DB in case acknowledged via UI/API
        if not self._acknowledged and self._interrupt_id is not None:
            is_acked_in_db = await workflow.execute_activity(
                activity_check_acknowledgement,
                self._interrupt_id,
                start_to_close_timeout=timedelta(seconds=10),
            )
            if is_acked_in_db:
                self._acknowledged = True

        # Step 3: Escalate once if unacknowledged
        if not self._acknowledged and not self._escalated and self._interrupt_id is not None:
            await workflow.execute_activity(
                activity_send_escalation_alert,
                args=[self._interrupt_id, item.title, item.body, item.reason],
                start_to_close_timeout=timedelta(seconds=15),
            )
            self._escalated = True

        return {
            "interrupt_id": self._interrupt_id,
            "acknowledged": self._acknowledged,
            "escalated": self._escalated,
            "verdict": self._verdict,
        }


@workflow.defn
class HushCadenceWorkflow:
    """
    3-Hour Durable Cadence Workflow:
    - Maintains exact 3-hour cadence across laptop sleep and process restarts.
    - Ingests -> Classifies with local model retries -> Fans out interrupts -> Generates brief.
    - Determinism boundary: all I/O, DB reads, model calls live strictly in activities.
    """

    def __init__(self):
        self._cycle_count: int = 0
        self._last_brief: Optional[BriefSummary] = None
        self._is_running: bool = True

    @workflow.query
    def get_cadence_status(self) -> Dict[str, Any]:
        return {
            "cycle_count": self._cycle_count,
            "is_running": self._is_running,
            "last_brief_id": self._last_brief.brief_id if self._last_brief else None,
            "last_cut_count": self._last_brief.cut_count if self._last_brief else None,
            "next_brief_time": self._last_brief.next_brief_time if self._last_brief else None,
        }

    @workflow.signal
    def stop(self):
        self._is_running = False

    @workflow.run
    async def run(self, interval_seconds: int = 10800, max_cycles: Optional[int] = None) -> int:
        while self._is_running:
            self._cycle_count += 1

            # 1. Ingest from macOS database
            await workflow.execute_activity(
                activity_ingest_notifications,
                start_to_close_timeout=timedelta(seconds=30),
            )

            # 2. Classify pending with local model (using activity retry policy)
            classified_items = await workflow.execute_activity(
                activity_classify_pending,
                args=[20],
                start_to_close_timeout=timedelta(seconds=180),
                retry_policy=LOCAL_MODEL_RETRY_POLICY,
            )

            # 3. For any emergency interrupts, spawn child escalation workflows
            for item in classified_items:
                if item.is_interrupt:
                    await workflow.start_child_workflow(
                        HushInterruptEscalationWorkflow.run,
                        item,
                        id=f"interrupt-escalation-{item.notification_id}",
                    )

            # 4. Generate the 4-line brief
            self._last_brief = await workflow.execute_activity(
                activity_generate_brief,
                args=[3],
                start_to_close_timeout=timedelta(seconds=20),
            )

            if max_cycles and self._cycle_count >= max_cycles:
                break

            # 5. Durable sleep across laptop sleep
            await workflow.sleep(timedelta(seconds=interval_seconds))

        return self._cycle_count
