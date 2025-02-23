#!/bin/bash

echo "Checking if RabbitMQ container exists..."
if [ "$(docker ps -aq -f name=rabbitmq)" ]; then
    echo "Found existing RabbitMQ container. Removing it..."
    docker rm -f rabbitmq
fi

echo "Starting new RabbitMQ container..."
docker run -d --name rabbitmq \
    -p 5672:5672 \
    -p 15672:15672 \
    --hostname rabbitmq \
    -e RABBITMQ_DEFAULT_USER=guest \
    -e RABBITMQ_DEFAULT_PASS=guest \
    rabbitmq:management

echo "Waiting for RabbitMQ to start up..."
sleep 10  

echo "RabbitMQ container status:"
docker ps | grep rabbitmq

echo "RabbitMQ Management Interface is available at:"
echo "http://127.0.0.1:15672"
echo "Username: guest"
echo "Password: guest"