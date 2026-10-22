import pytest
from datetime import timedelta
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from hush.temporal.workflows import (
    HushInterruptEscalationWorkflow,
    HushCadenceWorkflow,
    TASK_QUEUE_NAME,
)
from hush.temporal.activities import (
    activity_ingest_notifications,
    activity_classify_pending,
    activity_generate_brief,
    activity_send_interrupt_alert,
    activity_check_acknowledgement,
    activity_send_escalation_alert,
    ClassificationItem,
)
from hush.db import init_db


@pytest.mark.asyncio
async def test_temporal_escalation_workflow_unacknowledged(tmp_path):
    """
    Verifies that unacknowledged interrupts escalate exactly ONCE after 10 minutes.
    Temporal time-skipping advances the 10-minute durable timer instantaneously.
    """
    db_file = tmp_path / "test_temporal.db"
    init_db(db_file)

    async with await WorkflowEnvironment.start_time_skipping() as env:
        worker = Worker(
            env.client,
            task_queue=TASK_QUEUE_NAME,
            workflows=[HushInterruptEscalationWorkflow],
            activities=[
                activity_send_interrupt_alert,
                activity_check_acknowledgement,
                activity_send_escalation_alert,
            ],
        )

        test_item = ClassificationItem(
            notification_id="test-temporal-01",
            urgency=0.95,
            category="health",
            score=0.95,
            reason="ER Hospital Alert",
            is_interrupt=True,
            title="City Hospital ER",
            body="Patient emergency contact needed immediately.",
        )

        async with worker:
            handle = await env.client.start_workflow(
                HushInterruptEscalationWorkflow.run,
                test_item,
                id="test-escalation-unacked",
                task_queue=TASK_QUEUE_NAME,
            )

            # Advance time past the 10-minute acknowledgement window
            result = await handle.result()

            assert result["escalated"] is True
            assert result["acknowledged"] is False


@pytest.mark.asyncio
async def test_temporal_escalation_workflow_acknowledged_signal(tmp_path):
    """
    Verifies that when user acknowledges via signal, escalation is suppressed.
    """
    db_file = tmp_path / "test_temporal_acked.db"
    init_db(db_file)

    async with await WorkflowEnvironment.start_time_skipping() as env:
        worker = Worker(
            env.client,
            task_queue=TASK_QUEUE_NAME,
            workflows=[HushInterruptEscalationWorkflow],
            activities=[
                activity_send_interrupt_alert,
                activity_check_acknowledgement,
                activity_send_escalation_alert,
            ],
        )

        test_item = ClassificationItem(
            notification_id="test-temporal-02",
            urgency=0.90,
            category="money",
            score=0.90,
            reason="Fraudulent debit",
            is_interrupt=True,
            title="Chase Fraud Alert",
            body="Suspicious debit of $2,400.",
        )

        async with worker:
            handle = await env.client.start_workflow(
                HushInterruptEscalationWorkflow.run,
                test_item,
                id="test-escalation-acked",
                task_queue=TASK_QUEUE_NAME,
            )

            # Signal acknowledgement within the 10-minute window
            await handle.signal(HushInterruptEscalationWorkflow.acknowledge, "useful")

            result = await handle.result()
            assert result["acknowledged"] is True
            assert result["escalated"] is False


@pytest.mark.asyncio
async def test_temporal_cadence_workflow_cycle(tmp_path):
    """
    Verifies that the 3-hour cadence workflow executes all 4 stages deterministically:
    ingest -> classify -> fan-out interrupts -> brief generation.
    """
    db_file = tmp_path / "test_cadence.db"
    init_db(db_file)

    async with await WorkflowEnvironment.start_time_skipping() as env:
        worker = Worker(
            env.client,
            task_queue=TASK_QUEUE_NAME,
            workflows=[
                HushCadenceWorkflow,
                HushInterruptEscalationWorkflow,
            ],
            activities=[
                activity_ingest_notifications,
                activity_classify_pending,
                activity_generate_brief,
                activity_send_interrupt_alert,
                activity_check_acknowledgement,
                activity_send_escalation_alert,
            ],
        )

        async with worker:
            cycles = await env.client.execute_workflow(
                HushCadenceWorkflow.run,
                args=[10800, 1],  # 3-hour interval, max 1 cycle
                id="test-cadence-workflow",
                task_queue=TASK_QUEUE_NAME,
            )
            assert cycles == 1
