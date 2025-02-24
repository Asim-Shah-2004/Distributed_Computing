import xmlrpc.client

server = xmlrpc.client.ServerProxy('http://10.0.2.13:8000')

a = int(input("Enter a: "))
b = int(input("Enter b: "))

add_result = server.add(a, b)
subtract_result = server.subtract(a, b)
multiply_result = server.multiply(a, b)
divide_result = server.divide(a, b)

print(f"Addition: {a} + {b} = {add_result}")
print(f"Subtraction: {a} - {b} = {subtract_result}")
print(f"Multiplication: {a} * {b} = {multiply_result}")
print(f"Division: {a} / {b} = {divide_result}")