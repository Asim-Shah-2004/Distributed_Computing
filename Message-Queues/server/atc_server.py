import pika
import json
import time
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

logging.getLogger("pika").setLevel(logging.WARNING)
logging.getLogger("pika.connection").setLevel(logging.WARNING)
logging.getLogger("pika.channel").setLevel(logging.WARNING)

class ATCServer:
    def __init__(self):
        self.runways = {
            'Runway1': {'status': 'available', 'aircraft': None},
            'Runway2': {'status': 'available', 'aircraft': None}
        }
        self.aircraft_status = {}
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1'))
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange='atc_exchange', exchange_type='topic', durable=False)
        self.channel.queue_declare(queue='landing_requests', durable=True)
        self.channel.queue_declare(queue='emergency_requests', durable=True)
        self.channel.queue_declare(queue='status_updates', durable=True)
        self.channel.queue_bind(exchange='atc_exchange', queue='landing_requests', routing_key='landing.#')
        self.channel.queue_bind(exchange='atc_exchange', queue='emergency_requests', routing_key='emergency.#')
        self.channel.queue_bind(exchange='atc_exchange', queue='status_updates', routing_key='status.#')
        logging.info("ATC Server ready")

    def get_available_runway(self):
        for runway, info in self.runways.items():
            if info['status'] == 'available':
                return runway
        return None

    def handle_landing_request(self, ch, method, properties, body):
        data = json.loads(body)
        aircraft_id = data['aircraft_id']
        logging.info(f"Processing landing request from Aircraft {aircraft_id}")
        time.sleep(10)
        runway = self.get_available_runway()
        response = {
            'aircraft_id': aircraft_id,
            'timestamp': datetime.now().isoformat()
        }
        if runway:
            self.runways[runway]['status'] = 'occupied'
            self.runways[runway]['aircraft'] = aircraft_id
            response.update({
                'status': 'approved',
                'runway': runway,
                'message': f'Clear to land on {runway}'
            })
            logging.info(f"Aircraft {aircraft_id}: Cleared for {runway}")
        else:
            response.update({
                'status': 'denied',
                'message': 'All runways occupied, please hold'
            })
            logging.info(f"Aircraft {aircraft_id}: Holding - no runways")
        self.channel.basic_publish(
            exchange='atc_exchange',
            routing_key=f'response.{aircraft_id}',
            body=json.dumps(response)
        )
        logging.info(f"Response sent to Aircraft {aircraft_id}")

    def handle_emergency_request(self, ch, method, properties, body):
        data = json.loads(body)
        aircraft_id = data['aircraft_id']
        emergency_type = data.get('emergency_type', 'unspecified')
        logging.info(f"Processing EMERGENCY request from Aircraft {aircraft_id} - Type: {emergency_type}")
        time.sleep(2)
        runway = self.get_available_runway()
        response = {
            'aircraft_id': aircraft_id,
            'timestamp': datetime.now().isoformat()
        }
        if runway:
            self.runways[runway]['status'] = 'occupied'
            self.runways[runway]['aircraft'] = aircraft_id
            response.update({
                'status': 'emergency_approved',
                'runway': runway,
                'message': f'EMERGENCY CLEARANCE GRANTED for {runway}'
            })
            logging.info(f"EMERGENCY: Aircraft {aircraft_id} cleared for {runway}")
        else:
            for runway, info in self.runways.items():
                if info['aircraft']:
                    self.runways[runway]['status'] = 'available'
                    self.runways[runway]['aircraft'] = aircraft_id
                    response.update({
                        'status': 'emergency_approved',
                        'runway': runway,
                        'message': f'EMERGENCY CLEARANCE GRANTED for {runway} - Other traffic diverted'
                    })
                    logging.info(f"EMERGENCY: Aircraft {aircraft_id} cleared for {runway} - Traffic diverted")
                    break
        self.channel.basic_publish(
            exchange='atc_exchange',
            routing_key=f'response.{aircraft_id}',
            body=json.dumps(response)
        )
        logging.info(f"Emergency response sent to Aircraft {aircraft_id}")

    def start(self):
        self.channel.basic_consume(
            queue='landing_requests',
            on_message_callback=self.handle_landing_request,
            auto_ack=True
        )
        self.channel.basic_consume(
            queue='emergency_requests',
            on_message_callback=self.handle_emergency_request,
            auto_ack=True
        )
        logging.info("ATC Server started")
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.connection.close()
            logging.info("ATC Server stopped")

if __name__ == '__main__':
    server = ATCServer()
    server.start()