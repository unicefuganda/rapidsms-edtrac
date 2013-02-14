'''
Created on Feb 14, 2013

@author: raybesiga
'''

from django.core.management.base import BaseCommand
from education.models import reschedule_weekly_script
from optparse import OptionParser, make_option

class Command(BaseCommand):

    option_list = BaseCommand.option_list + (
#        make_option("-d", "--date", dest="date"),
        make_option("-g", "--group", dest="group"),
        make_option("-s", "--slug", dest="slug"),
    )
    def handle(self, **options):

#        if not options['date']:
#            date = raw_input('Date when questions should be sent out -- YYYY-MM-DD:')
#        else:
#            date = options['date']
        if not options['group']:
            group = raw_input('Group -- Teachers or Head Teachers:')
        else:
            group = 'all'
        if not options['slug']:
            slug = raw_input('Slug of script you wish to reschedule -- edtrac_p3_teachers_weekly')
        else:
            slug = 'edtrac_p3_teachers_weekly'

        reschedule_weekly_script(grp=group, slug=slug)
        self.stdout.write('')
        self.stdout.write('done!')