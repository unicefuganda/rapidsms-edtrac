from django.db import models
from django.conf import settings
from rapidsms.models import Contact
from eav.models import Attribute
from script.signals import script_progress_was_completed, script_progress
from script.models import *
from rapidsms.contrib.locations.models import Location
from rapidsms_xforms.models import XFormField, XForm, XFormSubmission, dl_distance, xform_received
from script.utils.handling import find_best_response, find_closest_match
from education.utils import _schedule_weekly_scripts, _schedule_monthly_script, _schedule_termly_script
import re
import calendar
from django.conf import settings
import datetime
import time
from difflib import get_close_matches
from django.db.models import Sum
from django.forms import ValidationError
from django.contrib.auth.models import Group, User
from rapidsms_httprouter.models import mass_text_sent


class School(models.Model):
    name = models.CharField(max_length=160)
    emis_id = models.CharField(max_length=10)
    location = models.ForeignKey(Location, related_name='schools')

    def __unicode__(self):
        return '%s' % self.name


class EmisReporter(Contact):
    CLASS_CHOICES = (
        ('P3', 'Primary Three'),
        ('P6', 'Primary Six'),
    )

    grade = models.CharField(max_length=2, choices=CLASS_CHOICES, null=True)
    schools = models.ManyToManyField(School, null=True)

    class Meta:
        ordering = ["name"]

    def __unicode__(self):
        return self.name
    
    def is_member_of(self, group):
        return group.lower() in [grp.lower for grp in self.groups.objects.values_list('name', flat=True)]

    def schools_list(self):
        return self.schools.values_list('name', flat=True)

class Role(Group):
   class Meta:
       proxy = True
       permissions = (
            ("can_report", "can  send data and receive data via text messages"),
            ("can_view_one_school", "Access to View his/her school specific info"),
            ("can_view_all_schools", "Access to View information from all schools"),
            ("can_message_all", "Can send out mass text,polls etc "),
            ("can_message_one_district", "Can send mass text,polls etc to district schools"),
            ("can_view_one_district_verified", "Access to view verified district data "),
            ("can_view_one_district_unverified", "Access to view district unverified  data  "),
            ("can_edit_one_district", "Access to edit his/her district specific info"),
            ("can_verify_one_district", "Access to edit his/her district specific info"),
            ("can_export_one_district", "Access to export his/her district specific info"),
            ("can_export_all", "Access to export all data"),

        )
       
class UserProfile(models.Model):
    name = models.CharField(max_length=160)
    location = models.ForeignKey(Location)
    role = models.ForeignKey(Role)
    user = models.ForeignKey(User,related_name="profile")
    
    def is_member_of(self, group):
        return group.lower() == self.role.name.lower()

    def __unicode__(self):
        return self.name
    
class ScriptSchedule(models.Model):
    script = models.ForeignKey(Script)
    date = models.DateTimeField(auto_now=True)

def parse_date(command, value):
    return parse_date_value(value)

def parse_gender(gender):
    gender = get_close_matches(gender, ['M', 'Male', 'F', 'Female'], 1, 0.6)
    try:
        return list(gender[0])[0]
    except:
        return None 
    
def parse_grade(grade):
    grade = get_close_matches(grade, ['P 3', 'P3','p3', 'P 6', 'P6', 'p6'], 1, 0.6)
    try:
        cls = list(grade[0])[1] if list(grade[0])[1].strip() else list(grade[0])[2]
        return (list(grade[0])[0]).upper() + cls
    except:
        return None 


def parse_date_value(value):
    try:
        date_expr = re.compile(r"\d{1,2} (?:%s) \d{2,4}" % '|'.join(calendar.month_abbr[1:]))
        date_expr1 = re.compile(r"\d{1,2}-\d{1,2}-\d{2,4}")
        date_expr2 = re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}")
        date_expr3 = re.compile(r"\d{1,2}\.\d{1,2}\.\d{2,4}")
        date_expr4 = re.compile(r"\d{2,4}\.\d{1,2}\.\d{1,2}")
        date_expr5 = re.compile(r"\d{2,4}-\d{1,2}-\d{1,2}")

        if date_expr.match(value):
            dt_obj = datetime.datetime.strptime(value, "%d %b %Y")
        elif date_expr1.match(value):
            dt_obj = datetime.datetime.strptime(value, "%d-%m-%Y")
        elif date_expr2.match(value):
            dt_obj = datetime.datetime.strptime(value, "%d/%m/%Y")
        elif date_expr3.match(value):
            dt_obj = datetime.datetime.strptime(value, "%d.%m.%Y")
        elif date_expr4.match(value):
            dt_obj = datetime.datetime.strptime(value, "%Y.%m.%d")
        else:
            dt_obj = datetime.datetime.strptime(value, "%Y-%m-%d")

    except ValueError:
        raise ValidationError("Expected date format "
                "(\"dd mmm YYYY\", \"dd/mm/yyyy\", \"dd-mm-yyyy\", \"dd.mm.yyyy\", \"yyyy.mm.dd\" or \"yyyy-mm-dd\"), "
                "but instead received: %s." % value)

    time_tuple = dt_obj.timetuple()
    timestamp = time.mktime(time_tuple)
    return int(timestamp)


def parse_yesno(command, value):
    lvalue = value.lower().strip()
    if dl_distance(lvalue, 'yes') <= 1 or lvalue == 'y':
        return 1
    else:
        return 0
    
def parse_fuzzy_number(command, value):
    fuzzy_number = re.compile('([0-9oOI]+)|(None)', re.IGNORECASE)
    m = fuzzy_number.match(value)
    if m:
        num = value[m.start():m.end()]
        try:
            index_l = num.lower().index('None'.lower())
            num[:index_l] + '0' + num[index_l + len('None'):]
        except ValueError:
            num = num.replace('o', '0')
            num = num.replace('O', '0')
            num = num.replace('I', '1')

        remaining = value[m.end():].strip()
        if remaining:
            if len(remaining) > 50:
                remaining = "%s..." % remaining[:47]
            raise ValidationError('You need to send a number for %s, you sent %s.Please resend' % (command, remaining))
        else:
            return int(num)

# rewrite of parse_fuzzy_number
def parse_fuzzy_number_2(value):
    fuzzy_number = re.compile('([0-9oOI]+)|(None)', re.IGNORECASE)
    m = fuzzy_number.match(value)
    if m:
        num = value[m.start():m.end()]
        try:
            inder_lower = num.lower().index('None'.lower())
            num[:inder_lower] + '0' + num[inder_lower + len('None'):]
        except ValueError:
            num = num.replace('o', 'O')
            num = num.replace('O', '0')
            num = num.replace('I', '1')
        remaining = value[m.end():].strip()
        if remaining:
            if len(remaining) > 50:
                remaining= "%s..." % remaining[:47]
            raise ValidationError('You need to send a number. You sent %s. Please resend' % (remaining))
        else:
            return int(num)

def edtrac_autoreg(**kwargs):

    connection = kwargs['connection']
    progress = kwargs['sender']
    if not progress.script.slug == 'edtrac_autoreg':
        return
    session = ScriptSession.objects.filter(script=progress.script, connection=connection).order_by('-end_time')[0]
    script = progress.script

    role_poll = script.steps.get(poll__name='edtrac_role').poll
    gender_poll = script.steps.get(poll__name='edtrac_gender').poll
    class_poll = script.steps.get(poll__name='edtrac_class').poll
    district_poll = script.steps.get(poll__name='edtrac_district').poll
    subcounty_poll = script.steps.get(poll__name='edtrac_subcounty').poll
    school_poll = script.steps.get(poll__name='edtrac_school').poll
    name_poll = script.steps.get(poll__name='edtrac_name').poll
    
    name = find_best_response(session, name_poll)
    role = find_best_response(session, role_poll)
    gender = find_best_response(session, gender_poll)
    grade = find_best_response(session, class_poll)
    default_group = Group.objects.get(name='Other Reporters')
    subcounty = find_best_response(session, subcounty_poll)
    district = find_best_response(session, district_poll)

    if name:
        name = ' '.join([n.capitalize() for n in name.lower().split()])[:100]

    if subcounty:
        subcounty = find_closest_match(subcounty, Location.objects.filter(type__name='sub_county'))

    grp = find_closest_match(role, Group.objects)
    grp = grp if grp else default_group

    if subcounty:
        rep_location = subcounty
    elif district:
        rep_location = district
    else:
        rep_location = Location.tree.root_nodes()[0]
    try:
        contact = connection.contact or EmisReporter.objects.get(name=name, \
                                      reporting_location=rep_location, \
                                      groups=grp, \
                                      )
        if connection.contact:
            contact = EmisReporter.objects.get(pk=connection.contact.pk)
    except EmisReporter.DoesNotExist, EmisReporter.MultipleObectsReturned:
            contact = EmisReporter.objects.create()

    connection.contact = contact
    connection.save()

    group = Group.objects.get(name='Other Reporters')
    default_group = group
    if role:
        group = find_closest_match(role, Group.objects) or find_closest_match(role, Group.objects, True)
        if not group:
            group = default_group
    contact.groups.add(group)

    if subcounty:
        contact.reporting_location = subcounty
    elif district:
        contact.reporting_location = district
    else:
        contact.reporting_location = Location.tree.root_nodes()[0]

    if gender:
        gender = parse_gender(gender)
        if gender:
            contact.gender = gender
        
    if grade:
        grade = parse_grade(grade)
        if grade:
            contact.grade = grade

    if name:
        contact.name = name

    if not contact.name:
        contact.name = 'Anonymous User'
    contact.save()

    reporting_school = None
    school = find_best_response(session, school_poll)
    if school:
        if subcounty:
            reporting_school = find_closest_match(school, School.objects.filter(location__name__in=[subcounty], \
                                                                                location__type__name='sub_county'), True)
        elif district:
            reporting_school = find_closest_match(school, School.objects.filter(location__name__in=[district.name], \
                                                                            location__type__name='district'), True)
        else:
            reporting_school = find_closest_match(school, School.objects.filter(location__name=Location.tree.root_nodes()[0].name))
        if reporting_school:
            contact.schools.add(reporting_school)
            contact.save()

    if not getattr(settings, 'TRAINING_MODE', False):
        # Now that you have their roll, they should be signed up for the periodic polling
        _schedule_weekly_scripts(group, connection, ['Teachers', 'Head Teachers', 'SMC'])
        #_schedule_monthly_script(group, connection, 'edtrac_teachers_monthly', 'last', ['Teachers'])
        _schedule_monthly_script(group, connection, 'edtrac_head_teachers_monthly', 'last', ['Head Teachers'])
        _schedule_monthly_script(group, connection, 'edtrac_smc_monthly', 5, ['SMC'])
        _schedule_monthly_script(group, connection, 'edtrac_gem_monthly', 20, ['GEM'])
        #termly messages go out mid April, July or November by default, this can be overwridden by manual process
        _schedule_termly_script(group, connection, 'edtrac_head_teachers_termly', ['Head Teachers'])
        _schedule_termly_script(group, connection, 'edtrac_smc_termly', ['SMC'])

def edtrac_reschedule_script(**kwargs):
    connection = kwargs['connection']
    progress = kwargs['sender']
    slug = progress.script.slug
    if not progress.script.slug.startswith('edtrac_') or progress.script.slug == 'edtrac_autoreg':
        return
    if not connection.contact:
        return
    if not connection.contact.groups.count():
        return
    group = connection.contact.groups.all()[0]
    if slug in ["edtrac_%s" % g.lower().replace(' ', '_') + '_weekly' for g in ['Teachers', 'Head Teachers', 'SMC']]:
        _schedule_weekly_scripts(group, connection, ['Teachers', 'Head Teachers', 'SMC'])
    elif slug == 'edtrac_teachers_monthly':
        _schedule_monthly_script(group, connection, 'edtrac_teachers_monthly', 'last', ['Teachers'])
    elif slug == 'edtrac_head_teachers_monthly':
        _schedule_monthly_script(group, connection, 'edtrac_head_teachers_monthly', 'last', ['Head Teachers'])
    elif slug == 'edtrac_smc_monthly':
        _schedule_monthly_script(group, connection, 'edtrac_smc_monthly', 5, ['SMC'])
    elif slug == 'edtrac_gem_monthly':
        _schedule_monthly_script(group, connection, 'edtrac_gem_monthly', 20, ['GEM'])
    elif slug == 'edtrac_head_teachers_termly':
        _schedule_termly_script(group, connection, 'edtrac_head_teachers_termly', ['Head Teachers'])
    else:
        _schedule_termly_script(group, connection, 'edtrac_smc_termly', ['SMC'])

def edtrac_autoreg_transition(**kwargs):

    connection = kwargs['connection']
    progress = kwargs['sender']
    if not progress.script.slug == 'edtrac_autoreg':
        return
    script = progress.script
    try:
        session = ScriptSession.objects.filter(script=progress.script, connection=connection, end_time=None).latest('start_time')
    except ScriptSession.DoesNotExist:
        return
    role_poll = script.steps.get(poll__name="edtrac_role").poll
    role = find_best_response(session, role_poll)
    group = None

    if role:
        group = find_closest_match(role, Group.objects) or find_closest_match(role, Group.objects, True)
    skipsteps = {
        'edtrac_gender':['Head Teachers'],
        'edtrac_subcounty' : ['Teachers', 'Head Teachers', 'SMC', 'GEM'],
        'edtrac_class':['Teachers'],
        'edtrac_school':['Teachers', 'Head Teachers', 'SMC']
    }
    skipped = True
    while group and skipped:
        skipped = False
        for step_name, roles in skipsteps.items():
            if  progress.step.poll and \
                progress.step.poll.name == step_name and group.name not in roles:
                skipped = True
                progress.step = progress.script.steps.get(order=progress.step.order + 1)
                progress.save()
                break




def edtrac_attendance_script_transition(**kwargs):
    #import pdb; pdb.set_trace()
    connection = kwargs['connection']
    progress = kwargs['sender']
    if not progress.script.slug == 'edtrac_teachers_weekly':
        return
    script = progress.script
    try:
        session = ScriptSession.objects.filter(script=script, connection=connection, end_time=None).latest('start_time')
    except ScriptSession.DoesNotExist:
        return
    grade = connection.contact.emisreporter.grade
    if not grade:
        return
    skipsteps = {
        'edtrac_boysp3_attendance':['P3'],
        'edtrac_boysp6_attendance':['P6'],
        'edtrac_girlsp3_attendance':['P3'],
        'edtrac_girlsp6_attendance':['P6'],
    }
    skipped = True
    while grade and skipped:
        skipped = False
        for step_name, grades in skipsteps.items():
            if  progress.step.poll and \
                progress.step.poll.name == step_name and grade not in grades:
                skipped = True
                if progress.last_step():
                    progress.giveup()
                    return
                progress.step = progress.script.steps.get(order=progress.step.order + 1)
                progress.save()
                break
            
def edtrac_scriptrun_schedule(**kwargs):

    connection = kwargs['connection']
    progress = kwargs['sender']
    step = kwargs['step']
    if progress.script.slug == 'edtrac_autoreg':
        return
    script = progress.script
    connections = ScriptProgress.objects.filter(script=script)
    date = datetime.datetime.now().date()
    if step == 0:
        s, c = ScriptSchedule.objects.get_or_create(script=script, date__contains=date)
    
               
def reschedule_weekly_polls(grp=None):
    """
    manually reschedule all weekly polls or for a specified group
    """
    weekly_scripts = Script.objects.filter(slug__endswith='_weekly')
    if grp:
        slg_start = 'edtrac_%s'%grp.replace(' ','_').lower()
        weekly_scripts = weekly_scripts.filter(slug__startswith=slg_start)
        ScriptProgress.objects.filter(script__in=weekly_scripts)\
                                .exclude(connection__contact__emisreporter__groups__name__iexact=grp).delete()
    else:
        ScriptProgress.objects.filter(script__in=weekly_scripts).delete()
    Script.objects.filter(slug__in=weekly_scripts.values_list('slug', flat=True)).update(enabled=True)
    grps = Group.objects.filter(name__iexact=grp) if grp else Group.objects.filter(name__in=['Teachers', 'Head Teachers', 'SMC'])
    reps = EmisReporter.objects.filter(groups__in=grps)
    for rep in reps:
        if rep.default_connection and rep.groups.count() > 0:
            _schedule_weekly_scripts(rep.groups.all()[0], rep.default_connection, ['Teachers', 'Head Teachers', 'SMC'])
            

def reschedule_monthly_polls(grp=None):
    """
    manually reschedule all monthly polls or for a specified group
    """
    monthly_scripts = Script.objects.filter(slug__endswith='_monthly')
    if grp:
        slg_start = 'edtrac_%s'%grp.replace(' ','_').lower()
        monthly_scripts = monthly_scripts.filter(slug__startswith=slg_start)
        ScriptProgress.objects.filter(script__in=monthly_scripts)\
                                .exclude(connection__contact__emisreporter__groups__name__iexact=grp).delete()
    else:
        ScriptProgress.objects.filter(script__in=monthly_scripts).delete()
    Script.objects.filter(slug__in=monthly_scripts.values_list('slug', flat=True)).update(enabled=True)
    for slug in monthly_scripts.values_list('slug', flat=True):
        grps = Group.objects.filter(name__iexact=grp) if grp else Group.objects.filter(name__in=['Teachers', 'Head Teachers', 'SMC', 'GEM'])
        reps = EmisReporter.objects.filter(groups__in=grps)
        for rep in reps:
            if rep.default_connection and rep.groups.count() > 0:
                if slug == 'edtrac_teachers_monthly':
                    _schedule_monthly_script(rep.groups.all()[0], rep.default_connection, 'edtrac_teachers_monthly', 'last', ['Teachers'])
                elif slug == 'edtrac_head_teachers_monthly':
                    _schedule_monthly_script(rep.groups.all()[0], rep.default_connection, 'edtrac_head_teachers_monthly', 'last', ['Head Teachers'])
                elif slug == 'edtrac_smc_monthly':
                    _schedule_monthly_script(rep.groups.all()[0], rep.default_connection, 'edtrac_smc_monthly', 5, ['SMC'])
                elif slug == 'edtrac_gem_monthly':
                    _schedule_monthly_script(rep.groups.all()[0], rep.default_connection, 'edtrac_gem_monthly', 20, ['GEM'])
        
def reschedule_termly_polls(grp = 'all', date=None):
        
    """
    manually reschedule all termly polls or for a specified group
    """
    termly_scripts = Script.objects.filter(slug__endswith='_termly')
    if not grp == 'all':
        slg_start = 'edtrac_%s'%grp.replace(' ','_').lower()
        termly_scripts = termly_scripts.filter(slug__startswith=slg_start)
        ScriptProgress.objects.filter(script__in=termly_scripts)\
                                .exclude(connection__contact__emisreporter__groups__name__iexact=grp).delete()
    else:
        ScriptProgress.objects.filter(script__in=termly_scripts).delete()
    Script.objects.filter(slug__in=termly_scripts.values_list('slug', flat=True)).update(enabled=True)
    for slug in termly_scripts.values_list('slug', flat=True):
        grps = Group.objects.filter(name__iexact=grp) if not grp == 'all' else Group.objects.filter(name__in=['Head Teachers', 'SMC'])
        reps = EmisReporter.objects.filter(groups__in=grps)
        for rep in reps:
            if rep.default_connection and rep.groups.count() > 0:
                _schedule_termly_script(rep.groups.all()[0], rep.default_connection, slug, ['Head Teachers', 'SMC'], date)


Poll.register_poll_type('date', 'Date Response', parse_date_value, db_type=Attribute.TYPE_OBJECT)

XFormField.register_field_type('emisdate', 'Date', parse_date,
                               db_type=XFormField.TYPE_INT, xforms_type='integer')

XFormField.register_field_type('emisbool', 'YesNo', parse_yesno,
                               db_type=XFormField.TYPE_INT, xforms_type='integer')

XFormField.register_field_type('fuzzynum', 'Fuzzy Numbers (o/0/none)', parse_fuzzy_number,
                               db_type=XFormField.TYPE_INT, xforms_type='integer')

script_progress_was_completed.connect(edtrac_autoreg, weak=False)
script_progress_was_completed.connect(edtrac_reschedule_script, weak=False)
script_progress.connect(edtrac_autoreg_transition, weak=False)
script_progress.connect(edtrac_attendance_script_transition, weak=False)
#script_progress.connect(edtrac_scriptrun_schedule, weak=False)
