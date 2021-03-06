from django.core.management.base import BaseCommand
from poll.models import Poll
from rapidsms.messages.incoming import IncomingMessage
from education.models import EmisReporter
from rapidsms_httprouter.models import Message
from rapidsms_httprouter.router import get_router
from unregister.models import Blacklist
import random


def fake_incoming_message(message, connection):
    incomingmessage = IncomingMessage(connection, message)
    #router = get_router()
    #router.handle_incoming(connection.backend.name, connection.identity, message)
    
    incomingmessage.db_message = Message.objects.create(direction='I', connection=connection, text=message)
    incomingmessage.db_message.handled_by = 'poll'
    return incomingmessage

def fake_poll_responses(poll_name, grp):

    yesno_resp = ['yes', 'no']
    text_resp = ['0%', '25%', '50%', '75%', '100%']

    poll = Poll.objects.get(name=poll_name)
    rep_count = EmisReporter.objects.filter(groups__name=grp).count()

    for rep in EmisReporter.objects.exclude(connection__in=Blacklist.objects.values_list('connection',flat=True)).filter(groups__name=grp).distinct():
        if not rep.default_connection == None:
            if poll.type == Poll.TYPE_NUMERIC:
                poll.process_response(fake_incoming_message('%s' % random.randint(0,9), rep.default_connection))
                #poll.process_response(fake_incoming_message('%s' % random.choice(text_resp), rep.default_connection))
            if poll.name == 'edtrac_p3_curriculum_progress':
                poll.process_response(fake_incoming_message('%s'%random.choice([1.1, 1.2, 1.3, 2.1, 2.2, 2.3]), rep.default_connection))

            if poll.name == 'edtrac_smc_grants_test':
                poll.process_response(fake_incoming_message(random.choice(yesno_resp), rep.default_connection))

            elif poll.type == Poll.TYPE_TEXT:
            #            if poll.categories.values_list('name', flat=True)[0] in ['yes', 'no', 'unknown']:
            #                resp = random.choice(yesno_resp)
            #            else:
                resp = random.choice(text_resp)
                poll.process_response(fake_incoming_message(resp, rep.default_connection))
            elif poll.type == Poll.TYPE_CHOICES:
                pass
        #just ignore folks with no default connection
        pass

class Command(BaseCommand):
    def handle(self, *args, **options):
        poll_name = args[0]
        grp = args[1]
        fake_poll_responses(
            poll_name,
            grp
        )
        print "finished creating responses"