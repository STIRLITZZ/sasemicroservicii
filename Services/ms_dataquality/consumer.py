import json, os
from collections import deque
from confluent_kafka import Consumer
from validator import validate, normalize, dedup_key
from producer import make_producer, send

KAFKA = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
IN_TOPIC = "court.raw"
OUT_TOPIC = "court.validated"
MAX_DEDUP_SIZE = 10000  # Limit to prevent memory leak

consumer = Consumer({
    "bootstrap.servers": KAFKA,
    "group.id": "ms_dataquality",
    "auto.offset.reset": "earliest"
})

producer = make_producer(KAFKA)
consumer.subscribe([IN_TOPIC])

# Use deque for efficient bounded cache with FIFO eviction
seen_deque = deque(maxlen=MAX_DEDUP_SIZE)
seen = set()

while True:
    msg = consumer.poll(1.0)
    if msg is None:
        continue
    if msg.error():
        print(msg.error())
        continue

    event = json.loads(msg.value().decode("utf-8"))

    if not validate(event):
        continue

    event = normalize(event)
    key = dedup_key(event)

    if key in seen:
        continue

    # Maintain bounded cache: when deque evicts old item, remove from set
    if len(seen_deque) >= MAX_DEDUP_SIZE:
        oldest = seen_deque[0]
        seen.discard(oldest)

    seen_deque.append(key)
    seen.add(key)

    event["dedup_key"] = key
    send(producer, OUT_TOPIC, event)
