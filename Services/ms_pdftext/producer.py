import json
from confluent_kafka import Producer

def make_producer(bootstrap: str):
    return Producer({"bootstrap.servers": bootstrap})

def send(producer, topic: str, event: dict):
    producer.produce(
        topic,
        json.dumps(event, ensure_ascii=False).encode("utf-8")
    )
    producer.poll(0)
