from random import randint
from locust import HttpLocust, TaskSet, task


class UserBehavior(TaskSet):
    domains = list()

    def on_start(self):
        with open('data/urls_to_evaluate.txt', 'r') as urls:
            self.domains = urls.read().split('\n')

    @task(1)
    def apply(self):
        self.client.get("/apply?host={}".format(self.domains[randint(0, 199)]))


class WebsiteUser(HttpLocust):
    task_set = UserBehavior
    min_wait = 5000
    max_wait = 9000
