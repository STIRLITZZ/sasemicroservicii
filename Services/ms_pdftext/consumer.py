import json, os, requests
from confluent_kafka import Consumer
from pdf import download_pdf, extract_text
from storage import pdf_path, txt_path
from producer import make_producer, send

KAFKA = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")

consumer = Consumer({
    "bootstrap.servers": KAFKA,
    "group.id": "ms_pdftext",
    "auto.offset.reset": "earliest"
})

producer = make_producer(KAFKA)
consumer.subscribe(["court.validated"])

session = requests.Session()
session.headers["User-Agent"] = "Mozilla/5.0"

while True:
    msg = consumer.poll(1.0)
    if msg is None:
        continue
    if msg.error():
        print(msg.error())
        continue

    event = json.loads(msg.value().decode("utf-8"))

    pdf_file = pdf_path(event)
    if not os.path.exists(pdf_file):
        download_pdf(session, event["pdf_url"], pdf_file)

    text = extract_text(pdf_file)
    txt_file = txt_path(event)

    with open(txt_file, "w", encoding="utf-8") as f:
        f.write(text)

    out = {
        "dedup_key": event["dedup_key"],
        "instanta": event["instanta"],
        "dosar": event["dosar"],
        "pdf_path": pdf_file,
        "txt_path": txt_file,
        "text_chars": len(text),
        "status": "OK"
    }

    send(producer, "court.text", out)
