import asyncio
import os
from typing import Optional
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.testing import WorkflowEnvironment

from hush.temporal.workflows import (
    HushCadenceWorkflow,
    HushInterruptEscalationWorkflow,
    TASK_QUEUE_NAME,
)
from hush.temporal.activities import (
    activity_ingest_notifications,
    activity_classify_pending,
    activity_generate_brief,
    activity_send_interrupt_alert,
    activity_check_acknowledgement,
    activity_send_escalation_alert,
)
from hush.db import init_db

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")


async def run_worker(client: Optional[Client] = None):
    """Starts the Hush Temporal Worker for durable workflows."""
    init_db()

    if client is None:
        client = await Client.connect(TEMPORAL_HOST)

    worker = Worker(
        client,
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

    print(f"Hush Temporal Worker connected to {client.target_host}. Task Queue: {TASK_QUEUE_NAME}")
    await worker.run()


async def run_self_contained_demo():
    """Runs a complete end-to-end Temporal demo using an in-memory WorkflowEnvironment."""
    init_db()
    print("Starting self-contained Temporal workflow environment...")
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
            print("Worker active. Executing 1 full cycle of HushCadenceWorkflow...")
            result = await env.client.execute_workflow(
                HushCadenceWorkflow.run,
                args=[10800, 1],  # 3-hour interval, 1 cycle demo
                id="hush-cadence-demo",
                task_queue=TASK_QUEUE_NAME,
            )
            print(f"HushCadenceWorkflow completed cycle count: {result}")


if __name__ == "__main__":
    asyncio.run(run_self_contained_demo())
