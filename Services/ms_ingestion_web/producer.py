import json
from confluent_kafka import Producer


def make_producer(bootstrap_servers: str):
    """Creează producer optimizat cu batching și compression"""
    return Producer({
        "bootstrap.servers": bootstrap_servers,
        # Batching optimization
        "linger.ms": 100,  # Așteaptă 100ms pentru a acumula mesaje
        "batch.size": 65536,  # 64KB batch size
        # Compression pentru eficiență
        "compression.type": "lz4",  # Compresie rapidă
        # Network optimization
        "socket.keepalive.enable": True,
        # Reliability
        "acks": 1,  # Leader acknowledgment only (mai rapid decât all)
        "retries": 3,
    })


def send(producer: Producer, topic: str, event: dict):
    producer.produce(
        topic,
        json.dumps(event, ensure_ascii=False).encode("utf-8")
    )
    producer.poll(0)
