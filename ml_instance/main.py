import pika
import json
import os

HOST = os.environ["RABBITMQ_HOST"]
USERNAME = os.environ["RABBITMQ_USERNAME"]
PASSWORD = os.environ["RABBITMQ_PASSWORD"]

credentials = pika.PlainCredentials(USERNAME, PASSWORD)
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=HOST, port=5672, credentials=credentials)
)

channel = connection.channel()

channel.queue_declare(queue="rpc_queue")


def fib(n):
    if n == 0:
        return 0
    elif n == 1:
        return 1
    else:
        return fib(n - 1) + fib(n - 2)


def on_request(ch, method, props, body):
    n = int(json.loads(body)["text"])

    print(f" [.] fib({n})")
    response = {"tag": f"fib({n})", "keywords": [str(fib(n))]}

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
