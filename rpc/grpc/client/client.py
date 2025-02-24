import grpc
import computation_pb2
import computation_pb2_grpc
import os

def read_test_cases(filename):
    with open(filename, 'r') as f:
        t = int(f.readline())
        for _ in range(t):
            n = int(f.readline())
            array = list(map(int, f.readline().split()))
            yield n, array

def run():
    
    with grpc.insecure_channel('localhost:50051') as channel:
        
        stub = computation_pb2_grpc.ComputationStub(channel)
        
        
        input_path = os.path.join('data', 'input.txt')
        output_path = os.path.join('data', 'output.txt')
        
        
        with open(output_path, 'w') as out_file:
            for n, array in read_test_cases(input_path):
                
                request = computation_pb2.TestCase(
                    n=n,
                    array=array
                )
                
                
                response = stub.ProcessTestCase(request)
                
                
                out_file.write(f"{response.answer}\n")

if __name__ == '__main__':
    run()