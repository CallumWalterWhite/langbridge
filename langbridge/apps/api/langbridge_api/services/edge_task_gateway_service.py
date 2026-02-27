from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError

from langbridge.packages.common.langbridge_common.config import settings
from langbridge.packages.common.langbridge_common.contracts.runtime import (
    EdgeTaskAckRequest,
    EdgeTaskAckResponse,
    EdgeTaskFailRequest,
    EdgeTaskFailResponse,
    EdgeTaskLease,
    EdgeTaskPullRequest,
    EdgeTaskResultRequest,
    EdgeTaskResultResponse,
)
from langbridge.packages.common.langbridge_common.db.runtime import EdgeTaskRecord, EdgeTaskStatus
from langbridge.packages.common.langbridge_common.errors.application_errors import BusinessValidationError
from langbridge.packages.common.langbridge_common.repositories.edge_task_repository import (
    EdgeResultReceiptRepository,
    EdgeTaskRepository,
)
from langbridge.packages.messaging.langbridge_messaging.contracts.messages import MessageEnvelope
from langbridge.packages.messaging.langbridge_messaging.contracts.stream_mapping import STREAM_MAPPING


class EdgeTaskGatewayService:
    def __init__(
        self,
        edge_task_repository: EdgeTaskRepository,
        edge_result_receipt_repository: EdgeResultReceiptRepository,
    ) -> None:
        self._edge_task_repository = edge_task_repository
        self._edge_result_receipt_repository = edge_result_receipt_repository
        self._redis = Redis.from_url(self._build_redis_url(), decode_responses=True)
        self._redis_prefix = settings.EDGE_REDIS_PREFIX

    @staticmethod
    def _build_redis_url() -> str:
        return f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"

    def _pending_key(self, *, tenant_id: uuid.UUID, runtime_id: uuid.UUID) -> str:
        return f"{self._redis_prefix}:tenant:{tenant_id}:runtime:{runtime_id}:pending"

    def _leases_key(self, *, tenant_id: uuid.UUID, runtime_id: uuid.UUID) -> str:
        return f"{self._redis_prefix}:tenant:{tenant_id}:runtime:{runtime_id}:leases"

    def _task_key(self, task_id: uuid.UUID) -> str:
        return f"{self._redis_prefix}:task:{task_id}"

    async def enqueue_for_runtime(
        self,
        *,
        tenant_id: uuid.UUID,
        runtime_id: uuid.UUID,
        envelope: MessageEnvelope,
    ) -> uuid.UUID:
        task = EdgeTaskRecord(
            tenant_id=tenant_id,
            message_type=str(envelope.message_type),
            message_payload=json.loads(envelope.to_json()),
            target_runtime_id=runtime_id,
            status=EdgeTaskStatus.queued,
            max_attempts=envelope.headers.max_attempts or 5,
            enqueued_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._edge_task_repository.add(task)
        await self._edge_task_repository.flush()

        now_ts = datetime.now(timezone.utc).timestamp()
        task_key = self._task_key(task.id)
        await self._redis.hset(
            task_key,
            mapping={
                "id": str(task.id),
                "tenant_id": str(tenant_id),
                "runtime_id": str(runtime_id),
                "status": EdgeTaskStatus.queued.value,
                "message_type": str(envelope.message_type),
                "envelope": envelope.to_json(),
                "attempt_count": "0",
                "max_attempts": str(task.max_attempts),
            },
        )
        await self._redis.zadd(
            self._pending_key(tenant_id=tenant_id, runtime_id=runtime_id),
            {str(task.id): now_ts},
        )
        return task.id

    async def pull_tasks(
        self,
        *,
        tenant_id: uuid.UUID,
        runtime_id: uuid.UUID,
        request: EdgeTaskPullRequest,
    ) -> list[EdgeTaskLease]:
        leases: list[EdgeTaskLease] = []
        deadline = asyncio.get_running_loop().time() + request.long_poll_seconds
        while asyncio.get_running_loop().time() < deadline and len(leases) < request.max_tasks:
            await self._requeue_expired_leases(tenant_id=tenant_id, runtime_id=runtime_id)
            claimed = await self._claim_one_task(
                tenant_id=tenant_id,
                runtime_id=runtime_id,
                visibility_timeout_seconds=request.visibility_timeout_seconds,
            )
            if claimed is not None:
                leases.append(claimed)
                continue
            await asyncio.sleep(0.5)
        return leases

    async def ack_task(
        self,
        *,
        tenant_id: uuid.UUID,
        runtime_id: uuid.UUID,
        request: EdgeTaskAckRequest,
    ) -> EdgeTaskAckResponse:
        task_key = self._task_key(request.task_id)
        current = await self._redis.hgetall(task_key)
        if not current:
            raise BusinessValidationError("Task lease does not exist.")
        if current.get("lease_id") != request.lease_id:
            raise BusinessValidationError("Task lease does not match.")
        if current.get("runtime_id") != str(runtime_id):
            raise BusinessValidationError("Task lease belongs to a different runtime.")

        await self._redis.zrem(self._leases_key(tenant_id=tenant_id, runtime_id=runtime_id), str(request.task_id))
        await self._redis.hset(
            task_key,
            mapping={
                "status": EdgeTaskStatus.acked.value,
                "lease_id": "",
                "lease_expires_at": "",
                "leased_to_runtime_id": "",
            },
        )
        await self._redis.expire(task_key, 86400)

        task = await self._edge_task_repository.get_by_id(request.task_id)
        if task is not None:
            task.status = EdgeTaskStatus.acked
            task.lease_id = None
            task.lease_expires_at = None
            task.leased_to_runtime_id = None
            task.acked_at = datetime.now(timezone.utc)
        return EdgeTaskAckResponse(status=EdgeTaskStatus.acked.value)

    async def fail_task(
        self,
        *,
        tenant_id: uuid.UUID,
        runtime_id: uuid.UUID,
        request: EdgeTaskFailRequest,
    ) -> EdgeTaskFailResponse:
        task_key = self._task_key(request.task_id)
        current = await self._redis.hgetall(task_key)
        if not current:
            raise BusinessValidationError("Task lease does not exist.")
        if current.get("lease_id") != request.lease_id:
            raise BusinessValidationError("Task lease does not match.")
        if current.get("runtime_id") != str(runtime_id):
            raise BusinessValidationError("Task lease belongs to a different runtime.")

        attempt_count = int(current.get("attempt_count", "0"))
        max_attempts = int(current.get("max_attempts", "5"))
        next_status = EdgeTaskStatus.queued
        if attempt_count >= max_attempts:
            next_status = EdgeTaskStatus.dead_letter

        await self._redis.zrem(self._leases_key(tenant_id=tenant_id, runtime_id=runtime_id), str(request.task_id))
        if next_status == EdgeTaskStatus.dead_letter:
            await self._redis.hset(
                task_key,
                mapping={
                    "status": EdgeTaskStatus.dead_letter.value,
                    "last_error": request.error,
                },
            )
        else:
            available_at = datetime.now(timezone.utc).timestamp() + request.retry_delay_seconds
            await self._redis.hset(
                task_key,
                mapping={
                    "status": EdgeTaskStatus.queued.value,
                    "lease_id": "",
                    "lease_expires_at": "",
                    "leased_to_runtime_id": "",
                    "last_error": request.error,
                },
            )
            await self._redis.zadd(
                self._pending_key(tenant_id=tenant_id, runtime_id=runtime_id),
                {str(request.task_id): available_at},
            )

        task = await self._edge_task_repository.get_by_id(request.task_id)
        if task is not None:
            task.status = next_status
            task.lease_id = None
            task.lease_expires_at = None
            task.leased_to_runtime_id = None
            task.last_error = {"message": request.error}
            if next_status == EdgeTaskStatus.dead_letter:
                task.failed_at = datetime.now(timezone.utc)
        return EdgeTaskFailResponse(status=next_status.value)

    async def ingest_result(
        self,
        *,
        tenant_id: uuid.UUID,
        runtime_id: uuid.UUID,
        request: EdgeTaskResultRequest,
    ) -> EdgeTaskResultResponse:
        existing = await self._edge_result_receipt_repository.get_by_request_id(
            tenant_id=tenant_id,
            runtime_id=runtime_id,
            request_id=request.request_id,
        )
        if existing is not None:
            return EdgeTaskResultResponse(accepted=True, duplicate=True)

        payload_hash = hashlib.sha256(
            json.dumps(request.model_dump(mode="json"), sort_keys=True).encode("utf-8")
        ).hexdigest()

        try:
            await self._edge_result_receipt_repository.create_receipt(
                tenant_id=tenant_id,
                runtime_id=runtime_id,
                request_id=request.request_id,
                task_id=request.task_id,
                payload_hash=payload_hash,
            )
        except IntegrityError:
            return EdgeTaskResultResponse(accepted=True, duplicate=True)

        for envelope in request.envelopes:
            mapped_stream = STREAM_MAPPING.get(envelope.message_type)
            if mapped_stream is None:
                continue
            await self._redis.xadd(
                mapped_stream.value,
                {
                    "data": envelope.to_json(),
                    "type": str(envelope.message_type),
                },
            )

        return EdgeTaskResultResponse(accepted=True, duplicate=False)

    async def _requeue_expired_leases(self, *, tenant_id: uuid.UUID, runtime_id: uuid.UUID) -> None:
        now_ts = datetime.now(timezone.utc).timestamp()
        lease_key = self._leases_key(tenant_id=tenant_id, runtime_id=runtime_id)
        expired_task_ids = await self._redis.zrangebyscore(lease_key, min="-inf", max=now_ts, start=0, num=25)
        if not expired_task_ids:
            return

        pending_key = self._pending_key(tenant_id=tenant_id, runtime_id=runtime_id)
        for raw_task_id in expired_task_ids:
            task_id = uuid.UUID(raw_task_id)
            task_key = self._task_key(task_id)
            task_data = await self._redis.hgetall(task_key)
            await self._redis.zrem(lease_key, raw_task_id)
            if not task_data:
                continue
            if task_data.get("status") != EdgeTaskStatus.leased.value:
                continue

            max_attempts = int(task_data.get("max_attempts", "5"))
            attempt_count = int(task_data.get("attempt_count", "0"))
            if attempt_count >= max_attempts:
                await self._redis.hset(
                    task_key,
                    mapping={
                        "status": EdgeTaskStatus.dead_letter.value,
                        "lease_id": "",
                        "lease_expires_at": "",
                        "leased_to_runtime_id": "",
                    },
                )
                task = await self._edge_task_repository.get_by_id(task_id)
                if task is not None:
                    task.status = EdgeTaskStatus.dead_letter
                    task.lease_id = None
                    task.lease_expires_at = None
                    task.leased_to_runtime_id = None
                continue

            await self._redis.hset(
                task_key,
                mapping={
                    "status": EdgeTaskStatus.queued.value,
                    "lease_id": "",
                    "lease_expires_at": "",
                    "leased_to_runtime_id": "",
                },
            )
            await self._redis.zadd(pending_key, {raw_task_id: now_ts})

            task = await self._edge_task_repository.get_by_id(task_id)
            if task is not None:
                task.status = EdgeTaskStatus.queued
                task.lease_id = None
                task.lease_expires_at = None
                task.leased_to_runtime_id = None

    async def _claim_one_task(
        self,
        *,
        tenant_id: uuid.UUID,
        runtime_id: uuid.UUID,
        visibility_timeout_seconds: int,
    ) -> EdgeTaskLease | None:
        pending_key = self._pending_key(tenant_id=tenant_id, runtime_id=runtime_id)
        now_ts = datetime.now(timezone.utc).timestamp()
        candidates = await self._redis.zrangebyscore(
            pending_key,
            min="-inf",
            max=now_ts,
            start=0,
            num=1,
        )
        if not candidates:
            return None

        raw_task_id = candidates[0]
        removed = await self._redis.zrem(pending_key, raw_task_id)
        if not removed:
            return None

        task_id = uuid.UUID(raw_task_id)
        task_key = self._task_key(task_id)
        task_data = await self._redis.hgetall(task_key)
        if not task_data:
            return None

        lease_id = str(uuid.uuid4())
        lease_expires_ts = now_ts + visibility_timeout_seconds
        attempt_count = int(task_data.get("attempt_count", "0")) + 1
        await self._redis.hset(
            task_key,
            mapping={
                "status": EdgeTaskStatus.leased.value,
                "lease_id": lease_id,
                "lease_expires_at": str(lease_expires_ts),
                "leased_to_runtime_id": str(runtime_id),
                "attempt_count": str(attempt_count),
            },
        )
        await self._redis.zadd(
            self._leases_key(tenant_id=tenant_id, runtime_id=runtime_id),
            {raw_task_id: lease_expires_ts},
        )

        task = await self._edge_task_repository.get_by_id(task_id)
        if task is not None:
            task.status = EdgeTaskStatus.leased
            task.lease_id = lease_id
            task.lease_expires_at = datetime.fromtimestamp(lease_expires_ts, tz=timezone.utc)
            task.leased_to_runtime_id = runtime_id
            task.attempt_count = attempt_count

        envelope_json = task_data.get("envelope")
        if not envelope_json:
            raise BusinessValidationError("Task payload is missing.")

        return EdgeTaskLease(
            task_id=task_id,
            lease_id=lease_id,
            delivery_attempt=attempt_count,
            envelope=MessageEnvelope.from_json(envelope_json),
        )
