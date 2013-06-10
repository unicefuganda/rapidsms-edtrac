'''
Created on Nov 1, 2011

@author: asseym
'''

from django.core.management.base import BaseCommand
from education.models import reschedule_weekly_polls
from optparse import OptionParser, make_option

class Command(BaseCommand):
    
    option_list = BaseCommand.option_list + (
        make_option("-g", "--group", dest="group"),
    )
    def handle(self, **options):
        if not options['group']:
            group = raw_input('For which group? -- Teachers, SMC, Head Teachers, All:')
        else:
            group = options['group']
        group = None if options['group'] == 'All' else group
        reschedule_weekly_polls(grp=group)
        self.stdout.write('')
        self.stdout.write('Done')