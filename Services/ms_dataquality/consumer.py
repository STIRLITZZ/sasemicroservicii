import json, os
from confluent_kafka import Consumer
from validator import validate, normalize, dedup_key
from producer import make_producer, send

KAFKA = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
IN_TOPIC = "court.raw"
OUT_TOPIC = "court.validated"

consumer = Consumer({
    "bootstrap.servers": KAFKA,
    "group.id": "ms_dataquality",
    "auto.offset.reset": "earliest"
})

producer = make_producer(KAFKA)
consumer.subscribe([IN_TOPIC])

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
    seen.add(key)

    event["dedup_key"] = key
    send(producer, OUT_TOPIC, event)
