import pika
import json
import os
import joblib
import numpy as np
import hdbscan


from yake import KeywordExtractor
import pymorphy2
import re


def work(text: str):
    morph = pymorphy2.MorphAnalyzer()

    extractor2 = KeywordExtractor(lan="ru", n=2, dedupLim=0.6, top=3)

    extractor1 = KeywordExtractor(lan="ru", n=1, dedupLim=0.6, top=3)

    def is_russian_word(word):
        russian_pattern = re.compile("[а-яё]+", re.I)
        return bool(russian_pattern.match(word))

    def normalize_tag(tag):
        parsed_tag = morph.parse(tag)[0]
        normalized_tag = parsed_tag.normal_form
        return normalized_tag

    k2 = extractor2.extract_keywords(text)
    k1 = extractor1.extract_keywords(text)

    keywords = k2[:1]
    keywords.extend(k1)
    keywords.extend(k1[1:])

    filtered_keywords = []

    for kw, score in keywords:
        nkw = normalize_tag(kw)
        kw = list(kw.split())

        f = 0
        s = []
        for i in range(len(kw)):
            if not is_russian_word(kw[i]):
                s.append(kw[i])
                continue
            if "новость" in nkw or " риа" in nkw or nkw == "риа":
                f = 1
                break
            parsed_word = morph.parse(kw[i])[0]
            if parsed_word.inflect({"nomn"}):
                singular_nominative = parsed_word.inflect({"nomn"}).word
                s.append(singular_nominative.title())

        if not f and len(s) > 0:
            filtered_keywords.append(" ".join(s))

    fk = list(set(filtered_keywords[:4]))
    return {"tag": "govno", "keywords": fk}


def work2(text: str):
    tfidf_model = joblib.load("models/tfidf.joblib")
    text = np.array([text])

    out = tfidf_model.transform(text)

    umap_model = joblib.load("models/umap_model-2.joblib")
    out = umap_model.transform(out)

    hdb_scan_model = joblib.load("models/hdbscan.joblib")

    final_res = None
    for _ in range(5):
        final_res = hdbscan.approximate_predict(hdb_scan_model, out)
        if final_res[0] != -1:
            break

    return final_res[0]


HOST = os.environ["RABBITMQ_HOST"]
USERNAME = os.environ["RABBITMQ_USERNAME"]
PASSWORD = os.environ["RABBITMQ_PASSWORD"]
credentials = pika.PlainCredentials(USERNAME, PASSWORD)
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=HOST, port=5672, credentials=credentials)
)

channel = connection.channel()

channel.queue_declare(queue="rpc_queue")


def on_request(ch, method, props, body):
    text = json.loads(body)["text"]
    print(f"Got {text}")

    response = work(text)

    ch.basic_publish(
        exchange="",
        routing_key=props.reply_to,
        properties=pika.BasicProperties(correlation_id=props.correlation_id),
        body=json.dumps(response),
    )
    ch.basic_ack(delivery_tag=method.delivery_tag)


channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue="rpc_queue", on_message_callback=on_request)

print(" [x] Awaiting RPC requests")
channel.start_consuming()
