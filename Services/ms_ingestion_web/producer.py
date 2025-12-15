import json
from confluent_kafka import Producer


def make_producer(bootstrap_servers: str):
    return Producer({
        "bootstrap.servers": bootstrap_servers
    })


def send(producer: Producer, topic: str, event: dict):
    producer.produce(
        topic,
        json.dumps(event, ensure_ascii=False).encode("utf-8")
    )
    producer.poll(0)
