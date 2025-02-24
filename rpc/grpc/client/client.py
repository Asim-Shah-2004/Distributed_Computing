import grpc
import computation_pb2
import computation_pb2_grpc
import os
import logging
import time
from datetime import datetime


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('client.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('grpc_client')

def read_test_cases(filename):
    try:
        with open(filename, 'r') as f:
            t = int(f.readline())
            logger.info(f"Reading {t} test cases from {filename}")
            for case_num in range(t):
                try:
                    n = int(f.readline())
                    array = list(map(int, f.readline().split()))
                    logger.debug(f"Test case {case_num + 1}: n={n}, array={array}")
                    yield n, array
                except Exception as e:
                    logger.error(f"Error reading test case {case_num + 1}: {str(e)}")
                    raise
    except FileNotFoundError:
        logger.error(f"Input file {filename} not found")
        raise
    except Exception as e:
        logger.error(f"Error reading input file: {str(e)}")
        raise

def run():
    start_time = time.time()
    logger.info("Starting gRPC client")
    
    
    channel_options = [
        ('grpc.enable_retries', 1),
        ('grpc.keepalive_timeout_ms', 10000),  
        ('grpc.keepalive_time_ms', 60000),    
    ]
    
    try:
        with grpc.insecure_channel('localhost:50051', options=channel_options) as channel:
            stub = computation_pb2_grpc.ComputationStub(channel)
            
            input_path = os.path.join('data', 'input.txt')
            output_path = os.path.join('data', 'output.txt')
            
            logger.info(f"Processing input from {input_path}")
            
            with open(output_path, 'w') as out_file:
                success_count = 0
                total_count = 0
                
                for n, array in read_test_cases(input_path):
                    total_count += 1
                    try:
                        request = computation_pb2.TestCase(
                            n=n,
                            array=array
                        )
                        
                        
                        start = time.time()
                        response = stub.ProcessTestCase(
                            request,
                            timeout=30  
                        )
                        duration = time.time() - start
                        
                        logger.info(f"Test case {total_count} processed in {duration:.2f} seconds")
                        out_file.write(f"{response.answer}\n")
                        success_count += 1
                        
                    except grpc.RpcError as rpc_error:
                        if rpc_error.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                            logger.error(f"Timeout processing test case {total_count}")
                        else:
                            logger.error(f"RPC error processing test case {total_count}: {rpc_error.details()}")
                        out_file.write("Error\n")
                    except Exception as e:
                        logger.error(f"Error processing test case {total_count}: {str(e)}")
                        out_file.write("Error\n")
            
            total_time = time.time() - start_time
            logger.info(f"Processing completed. Success: {success_count}/{total_count}")
            logger.info(f"Total execution time: {total_time:.2f} seconds")
            
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        raise

if __name__ == '__main__':
    try:
        run()
    except Exception as e:
        logger.critical(f"Application failed: {str(e)}")
        exit(1)