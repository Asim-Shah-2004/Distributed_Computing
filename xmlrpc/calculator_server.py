from xmlrpc.server import SimpleXMLRPCServer

def add(a, b):
    print(f"Adding {a} and {b}")
    return a + b

def subtract(a, b):
    print(f"Subtracting {a} and {b}")
    return a - b

def multiply(a, b):
    print(f"Multiplying {a} and {b}")
    return a * b

def divide(a, b):
    print(f"Dividing {a} and {b}")
    if b == 0:
        return "Error: Division by zero"
    return a / b

server = SimpleXMLRPCServer(('0.0.0.0', 8000))

# Register the functions with the server
server.register_function(add, 'add')
server.register_function(subtract, 'subtract')
server.register_function(multiply, 'multiply')
server.register_function(divide, 'divide')

print("Calculator server is running on port 8000 on all network interfaces...")
server.serve_forever()