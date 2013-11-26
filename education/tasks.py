from celery.task import Task, PeriodicTask
from celery.registry import tasks
from .models import EnrolledDeployedQuestionsAnswered, create_record_enrolled_deployed_questions_answered
from datetime import timedelta

from rapidsms.contrib.locations.models import Location
from .views import generate_dashboard_vars

class UpdateDashboardVarsCache(Task):
    run_every = timedelta(minutes=30)
    def run(self, **kwargs):
        location = Location.objects.get(name="Uganda")
        dash_vars = generate_dashboard_vars(location, bust_cache=True)
tasks.register(UpdateDashboardVarsCache)


class CreateSystemReport(Task):
    def run(self, **kwargs):
        if kwargs.has_key('role'):
            role = kwargs.get('role')
            if role in ['DFO', 'DEO']:
                pass
            else:
                pass
tasks.register(CreateSystemReport)

class CreateRecordEnrolledDeployedQuestionsAnswered(Task):
    def run(self, **kwargs):
        create_record_enrolled_deployed_questions_answered(model = EnrolledDeployedQuestionsAnswered)

tasks.register(CreateRecordEnrolledDeployedQuestionsAnswered)

class ProcessRecordCreation(PeriodicTask):
    run_every = timedelta(minutes = 5)
    def run(self, **kwargs):
        CreateRecordEnrolledDeployedQuestionsAnswered.delay()
        logger = self.get_logger(**kwargs)
        logger.info("Running  CreateRecordEnrolledDeployedQuestionsAnswered")
        return
tasks.register(ProcessRecordCreation)
