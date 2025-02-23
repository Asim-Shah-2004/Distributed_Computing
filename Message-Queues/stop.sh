#!/bin/bash

echo "Stopping RabbitMQ container..."
if [ "$(docker ps -q -f name=rabbitmq)" ]; then
    docker stop rabbitmq
    echo "Container stopped."
else
    echo "RabbitMQ container is not running."
fi

echo "Removing RabbitMQ container..."
if [ "$(docker ps -aq -f name=rabbitmq)" ]; then
    docker rm rabbitmq
    echo "Container removed."
else
    echo "No RabbitMQ container found to remove."
fi