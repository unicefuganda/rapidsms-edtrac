import difflib
from rapidsms.apps.base import AppBase
from script.models import Script, ScriptProgress
from django.conf import settings
from unregister.models import Blacklist
from uganda_common.utils import handle_dongle_sms

class App (AppBase):

    def handle (self, message):

        if handle_dongle_sms(message):
            return True

        if message.text.strip().lower() in [i.lower() for i in getattr(settings, 'OPT_OUT_WORDS', ['quit'])] or\
           difflib.get_close_matches(message.text.strip().lower(), getattr(settings, 'OPT_OUT_WORDS', ['quit'])):

            if Blacklist.objects.filter(connection=message.connection).exists():
                message.respond('You cannot send Quit to 6200 (EduTrac) more than once.')
                return
            else:
                # create a Blacklist object
                Blacklist.objects.create(connection=message.connection)

                if ScriptProgress.objects.filter(connection=message.connection).exists():
                    # rogue progress quit
                    ScriptProgress.objects.filter(connection=message.connection).delete()

                if (message.connection.contact):
                    message.connection.contact.active = False
                    message.connection.contact.save()
                message.respond(getattr(settings, 'OPT_OUT_CONFIRMATION', 'Thank you for your contribution to EduTrac. To rejoin the system, send join to 6200'))
                return True
                #                return True

        elif message.text.strip().lower() in [i.lower() for i in getattr(settings, 'OPT_IN_WORDS', ['join'])]:
            if not message.connection.contact:
                ScriptProgress.objects.create(script=Script.objects.get(slug="edtrac_autoreg"),\
                    connection=message.connection)
            elif Blacklist.objects.filter(connection=message.connection).count():
                Blacklist.objects.filter(connection=message.connection).delete()
                if not ScriptProgress.objects.filter(script__slug='edtrac_autoreg', connection=message.connection).count():
                    ScriptProgress.objects.create(script=Script.objects.get(slug="edtrac_autoreg"),\
                        connection=message.connection)
            else:
                message.respond("You are already in the system and do not need to 'Join' again.")
            return True

        elif Blacklist.objects.filter(connection=message.connection).count():
            return True
            # when all else fails, quit!
        return False