import json
from confluent_kafka import Producer

def make_producer(bootstrap: str):
    """Creează producer optimizat cu batching și compression"""
    return Producer({
        "bootstrap.servers": bootstrap,
        "linger.ms": 100,
        "batch.size": 65536,
        "compression.type": "lz4",
        "socket.keepalive.enable": True,
        "acks": 1,
        "retries": 3,
    })

def send(producer, topic: str, event: dict):
    producer.produce(
        topic,
        json.dumps(event, ensure_ascii=False).encode("utf-8")
    )
    producer.poll(0)
