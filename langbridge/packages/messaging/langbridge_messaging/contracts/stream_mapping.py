
from langbridge.packages.messaging.langbridge_messaging.broker.redis import RedisStreams
from langbridge.packages.messaging.langbridge_messaging.contracts.base import MessageType


STREAM_MAPPING = {
    MessageType.AGENT_JOB_REQUEST: RedisStreams.WORKER,
    MessageType.JOB_EVENT: RedisStreams.API,
    MessageType.TEST: RedisStreams.WORKER,
}
