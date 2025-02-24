import Pyro5.api


def main():
    ns = Pyro5.api.locate_ns(host="192.168.12.236")
    uri = ns.lookup("task.manager")
    task_manager = Pyro5.api.Proxy(uri)

    print("Connected to Task Manager!")

    while True:
        print("\nOptions: add, update, list, exit")
        command = input("Enter command: ").strip().lower()

        if command == "add":
            task_id = input("Task ID: ").strip()
            desc = input("Description: ").strip()
            print(task_manager.add_task(task_id, desc))

        elif command == "update":
            task_id = input("Task ID: ").strip()
            status = input("New Status: ").strip()
            print(task_manager.update_task(task_id, status))

        elif command == "list":
            tasks = task_manager.get_tasks()
            print("Tasks:", tasks)

        elif command == "exit":
            print("Exiting...")
            break

        else:
            print("Invalid command.")


if __name__ == "__main__":
    main()
