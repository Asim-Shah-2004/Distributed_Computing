import pika
import json
import time
import logging
import sys
from datetime import datetime
import threading


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)


for logger_name in [
    "pika", 
    "pika.connection", 
    "pika.channel", 
    "pika.adapters.utils.io_services_utils",
    "connection", 
    "connection.impl", 
    "adapters.blocking_connection"
]:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

class Aircraft:
    def __init__(self, aircraft_id):
        self.aircraft_id = aircraft_id
        self.logger = logging.getLogger(f"Aircraft_{aircraft_id}")
        self.should_reconnect = True
        self.connection = None
        self.channel = None
        self.callback_queue = None
        self.consumer_tag = None
        self.consumer_thread = None
        self.connect()

    def connect(self):
        try:
            if self.connection and not self.connection.is_closed:
                self.cleanup_connection()

            parameters = pika.ConnectionParameters(
                host='127.0.0.1',
                port=5672,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            
            self.channel.exchange_declare(
                exchange='atc_exchange',
                exchange_type='topic',
                durable=False  
            )
            
            
            timestamp = int(time.time())
            result = self.channel.queue_declare(
                queue=f'aircraft_{self.aircraft_id}_{timestamp}',
                exclusive=True,
                auto_delete=True
            )
            self.callback_queue = result.method.queue
            
            self.channel.queue_bind(
                exchange='atc_exchange',
                queue=self.callback_queue,
                routing_key=f'response.{self.aircraft_id}'
            )
            
            if not self.consumer_thread or not self.consumer_thread.is_alive():
                self.consumer_thread = threading.Thread(target=self.consume_messages)
                self.consumer_thread.daemon = True
                self.consumer_thread.start()

            self.logger.info("Connected to ATC")
            return True

        except Exception:
            return False  

    def cleanup_connection(self):
        """Clean up existing connection and channel"""
        try:
            if self.channel and self.channel.is_open:
                if self.consumer_tag:
                    self.channel.basic_cancel(self.consumer_tag)
                if self.callback_queue:
                    try:
                        self.channel.queue_delete(queue=self.callback_queue)
                    except:
                        pass
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            self.callback_queue = None
            self.consumer_tag = None
        except Exception:
            pass 

    def consume_messages(self):
        while self.should_reconnect:
            try:
                self.consumer_tag = self.channel.basic_consume(
                    queue=self.callback_queue,
                    on_message_callback=self.handle_response,
                    auto_ack=True
                )
                self.channel.start_consuming()
            except (pika.exceptions.ConnectionClosedByBroker,
                    pika.exceptions.AMQPChannelError,
                    pika.exceptions.AMQPConnectionError) as e:
                if self.should_reconnect:
                    time.sleep(2)
                    self.reconnect()
            except Exception as e:
                if self.should_reconnect:
                    time.sleep(2)
                    self.reconnect()

    def reconnect(self):
        while self.should_reconnect:
            if self.connect():
                break
            time.sleep(5) 

    def handle_response(self, ch, method, properties, body):
        try:
            response = json.loads(body)
            status = response.get('status')
            message = response.get('message', '')
            
            if status in ['emergency_approved', 'approved']:
                self.logger.info(f"Cleared: {message}")
            else:
                self.logger.warning(f"Not cleared: {message}")
        except json.JSONDecodeError:
            self.logger.error("Received invalid JSON message")
        except Exception as e:
            self.logger.error(f"Response error: {str(e)}")

    def publish_message(self, routing_key, message):
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                self.channel.basic_publish(
                    exchange='atc_exchange',
                    routing_key=routing_key,
                    body=json.dumps(message),
                    properties=pika.BasicProperties(
                        delivery_mode=2 
                    )
                )
                return True
            except Exception:
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2)
                    self.reconnect()
        return False

    def request_landing(self):
        message = {
            'aircraft_id': self.aircraft_id,
            'request_type': 'landing',
            'timestamp': datetime.now().isoformat()
        }
        
        self.logger.info("Requesting landing clearance")
        if self.publish_message('landing.request', message):
            self.logger.info("Request sent, awaiting response...")
        else:
            self.logger.error("Request failed")

    def declare_emergency(self, emergency_type):
        message = {
            'aircraft_id': self.aircraft_id,
            'request_type': 'emergency',
            'emergency_type': emergency_type,
            'timestamp': datetime.now().isoformat()
        }
        
        self.logger.critical(f"Declaring emergency: {emergency_type}")
        if self.publish_message('emergency.request', message):
            self.logger.info("Request sent")
        else:
            self.logger.error("Request failed")

    def cleanup(self):
        """Improved cleanup method"""
        self.should_reconnect = False
        try:
            if self.channel and self.channel.is_open:
                self.channel.stop_consuming()
            self.cleanup_connection()
            self.logger.info("Cleanup completed successfully")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python client.py <aircraft_id>")
        sys.exit(1)
        
    aircraft_id = sys.argv[1]
    aircraft = None
    
    try:
        aircraft = Aircraft(aircraft_id)
        
        while True:
            print("\nAvailable actions:")
            print("1. Request landing")
            print("2. Declare emergency")
            print("3. Exit")
            
            try:
                choice = input("Choose an action (1-3): ").strip()
                
                if choice == '1':
                    aircraft.request_landing()
                elif choice == '2':
                    emergency_type = input("Enter emergency type (fuel/medical/technical): ").strip()
                    aircraft.declare_emergency(emergency_type)
                elif choice == '3':
                    break
                else:
                    print("Invalid choice. Please select 1-3.")
                
                time.sleep(1) 
                
            except EOFError:
                break
            
    except KeyboardInterrupt:
        print("\nShutting down aircraft communications...")
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
    finally:
        if aircraft:
            aircraft.cleanup()