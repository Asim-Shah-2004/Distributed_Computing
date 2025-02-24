import Pyro5.api


@Pyro5.api.expose
class TaskManager:
    def __init__(self):
        self.tasks = {}

    def add_task(self, task_id, description):
        if task_id in self.tasks:
            return f"Task {task_id} already exists."
        self.tasks[task_id] = {"description": description, "status": "pending"}
        print(f"Task {task_id} added.")
        return f"Task {task_id} added."

    def update_task(self, task_id, status):
        if task_id not in self.tasks:
            return f"Task {task_id} not found."
        self.tasks[task_id]["status"] = status
        print(f"Task {task_id} updated to {status}.")
        return f"Task {task_id} updated to {status}."

    def get_tasks(self):
        return self.tasks


def main():
    daemon = Pyro5.server.Daemon()
    ns = Pyro5.api.locate_ns()
    uri = daemon.register(TaskManager)
    ns.register("task.manager", uri)

    print("Task Manager Server is running...")
    daemon.requestLoop()


if __name__ == "__main__":
    main()
