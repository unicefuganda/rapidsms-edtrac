# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
from datetime import datetime
import time
from unittest import TestCase
import dateutils
from django.conf import settings
from django.contrib.auth.models import Group, User
from education.models import schedule_script_now, EmisReporter, School
from education.test.utils import create_poll_with_reporters, create_group, create_location_type, create_location, create_school, create_emis_reporters, create_user_with_group, fake_incoming, create_attribute
from poll.models import Poll
from rapidsms.contrib.locations.models import Location, LocationType
from rapidsms_httprouter.models import Message
from script.models import Script, ScriptStep, ScriptProgress, ScriptSession
from script.utils.outgoing import check_progress
from education.view_helper_utils import *


class TestViewHelper(TestCase):
    def setUp(self):
        country = create_location_type("country")
        uganda_fields = {
            "rght": 15274,
            "level": 0,
            "tree_id": 1,
            "lft": 1,
        }
        self.uganda = create_location("uganda", country, **uganda_fields)
        admin_group = create_group("Admins")
        self.smc_group = create_group("SMC")
        self.admin_user = create_user_with_group("John", admin_group, self.uganda)

        district = create_location_type("district")
        kampala_fields = {
            "rght": 10901,
            "tree_parent": self.uganda,
            "level": 1,
            "tree_id": 1,
            "lft": 10686,
        }
        kampala_point = {
            "latitude": "0.3162800000",
            "longitude": "32.5821900000"
        }
        self.kampala_district = create_location("Kampala", district, point=kampala_point, **kampala_fields)
        self.kampala_school = create_school("St. Joseph's", self.kampala_district)
        self.kampala_school_lubaga = create_school("UMHS Lubaga", self.kampala_district)
        self.head_teacher_group = create_group("Head Teachers")
        self.emis_reporter1 = create_emis_reporters("dummy1", self.kampala_district, self.kampala_school, 12345,
                                                    self.head_teacher_group)
        self.emis_reporter1.grade = 'P3'
        self.emis_reporter1.gender = 'M'
        self.emis_reporter1.save()
        self.emis_reporter2 = create_emis_reporters("dummy2", self.kampala_district, self.kampala_school, 12346,
                                                    self.head_teacher_group)

        self.emis_reporter2.grade = 'P3'
        self.emis_reporter2.gender = 'M'
        self.emis_reporter2.save()

        self.emis_reporter3 = create_emis_reporters("dummy1", self.kampala_district, self.kampala_school, 12347,
                                                    self.smc_group)
        self.emis_reporter3.gender = 'F'
        self.emis_reporter3.save()

        self.p3_boys_absent_poll = create_poll_with_reporters("edtrac_boysp3_attendance",
                                                              "How many P3 boys are at school today?",
                                                              Poll.TYPE_NUMERIC, self.admin_user,
                                                              [self.emis_reporter1, self.emis_reporter2])
        self.p3_girls_absent_poll = create_poll_with_reporters("edtrac_girlsp3_attendance",
                                                               "How many P3 girls are at school today?",
                                                               Poll.TYPE_NUMERIC, self.admin_user,
                                                               [self.emis_reporter1, self.emis_reporter2])

        self.p3_boys_enroll_poll = create_poll_with_reporters("edtrac_boysp3_enrollment",
                                                              "How many boys are enrolled in P3 this term?",
                                                              Poll.TYPE_NUMERIC, self.admin_user,
                                                              [self.emis_reporter1])
        self.p3_girls_enroll_poll = create_poll_with_reporters("edtrac_girlsp3_enrollment",
                                                               "How many girls are enrolled in P3 this term?",
                                                               Poll.TYPE_NUMERIC, self.admin_user,
                                                               [self.emis_reporter1])
        self.head_teacher_monitoring_poll = create_poll_with_reporters("edtrac_head_teachers_attendance",
                                                                       "Has the head teacher been at school for at least 3 days? Answer YES or NO",
                                                                       Poll.TYPE_TEXT, self.admin_user,
                                                                       [self.emis_reporter3])
        self.teachers_weekly_script = Script.objects.create(name='Revised P3 Teachers Weekly Script',
                                                            slug='edtrac_p3_teachers_weekly')

        self.p3_boys_attendance_step = ScriptStep.objects.create(script=self.teachers_weekly_script,
                                                                 poll=self.p3_boys_absent_poll,
                                                                 order=0, rule=ScriptStep.WAIT_MOVEON, start_offset=0,
                                                                 giveup_offset=2)
        self.teachers_weekly_script.steps.add(self.p3_boys_attendance_step)

        self.p3_girls_attendance_step = ScriptStep.objects.create(script=self.teachers_weekly_script,
                                                                  poll=self.p3_girls_absent_poll,
                                                                  order=1, rule=ScriptStep.WAIT_MOVEON, start_offset=0,
                                                                  giveup_offset=2)
        self.teachers_weekly_script.steps.add(self.p3_girls_attendance_step)

        self.head_teachers_termly_script = Script.objects.create(name='P3 Enrollment Headteacher Termly Script',
                                                                 slug='edtrac_p3_enrollment_headteacher_termly')
        self.head_teacher_weekly_script = Script.objects.create(name='Education monitoring smc weekly script',
                                                                slug='edtrac_education_monitoring_smc_weekly_script')
        self.head_teachers_termly_script.steps.add(
            ScriptStep.objects.create(script=self.head_teachers_termly_script, poll=self.p3_boys_enroll_poll, order=0,
                                      rule=ScriptStep.WAIT_MOVEON, start_offset=0, giveup_offset=7200))

        self.head_teachers_termly_script.steps.add(
            ScriptStep.objects.create(script=self.head_teachers_termly_script, poll=self.p3_girls_enroll_poll, order=1,
                                      rule=ScriptStep.WAIT_MOVEON, start_offset=0, giveup_offset=7200))
        self.head_teacher_weekly_script.steps.add(
            ScriptStep.objects.create(script=self.head_teacher_weekly_script, poll=self.head_teacher_monitoring_poll,
                                      order=0,
                                      rule=ScriptStep.WAIT_MOVEON, start_offset=0, giveup_offset=7200)
        )

        settings.SCHOOL_TERM_START = dateutils.increment(datetime.datetime.today(), weeks=-4)
        settings.SCHOOL_TERM_END = dateutils.increment(datetime.datetime.today(), weeks=8)
        self.term_range = [getattr(settings, 'SCHOOL_TERM_START'), getattr(settings, 'SCHOOL_TERM_END')]

        create_attribute()

    def test_calculate_percent_should_return_50_when_given_1_and_2(self):
        self.assertEqual(50, compute_absent_values(1, 2))

    def test_calculate_percent_should_return_0_when_given_denominator_0(self):
        self.assertEqual(0, compute_absent_values(1, 0))

    def test_should_return_numeric_data_given_a_poll_location_and_time_range(self):
        schedule_script_now(self.head_teacher_group.name, slug=self.teachers_weekly_script.slug)
        check_progress(self.teachers_weekly_script)
        fake_incoming("20 boys", self.emis_reporter1)
        fake_incoming("10 boys", self.emis_reporter2)
        result = get_numeric_data([self.p3_boys_absent_poll], [self.kampala_district], self.term_range)
        self.assertEqual(30, result)


    def test_should_reject_numeric_data_thats_implausibly_large(self):
        schedule_script_now(self.head_teacher_group.name, slug=self.teachers_weekly_script.slug)
        check_progress(self.teachers_weekly_script)
        fake_incoming("20 boys", self.emis_reporter1)
        fake_incoming("5001 boys", self.emis_reporter2)
        result = get_numeric_data([self.p3_boys_absent_poll], [self.kampala_district], self.term_range)
        self.assertEqual(20, result)


    def test_should_return_location_numeric_data_given_a_poll_and_time_range(self):
        schedule_script_now(self.head_teacher_group.name, slug=self.teachers_weekly_script.slug)
        check_progress(self.teachers_weekly_script)
        fake_incoming("20 boys", self.emis_reporter1)
        fake_incoming("10 boys", self.emis_reporter2)
        result = get_numeric_data_for_location([self.p3_boys_absent_poll], [self.kampala_district], self.term_range)
        self.assertEqual(30, result[self.kampala_district.id])

    def test_should_return_get_numeric_data_by_school(self):
        schedule_script_now(self.head_teacher_group.name, slug=self.teachers_weekly_script.slug)
        check_progress(self.teachers_weekly_script)
        fake_incoming("20 boys", self.emis_reporter1)
        school_results = get_numeric_data_by_school([self.p3_boys_absent_poll], [self.kampala_school], self.term_range)
        self.assertEqual(20, sum(school_results))

    def test_should_return_get_numeric_data_all_schools_for_locations(self):
        schedule_script_now(self.head_teacher_group.name, slug=self.teachers_weekly_script.slug)
        check_progress(self.teachers_weekly_script)
        fake_incoming("20 boys", self.emis_reporter1)
        school_results = get_numeric_data_all_schools_for_locations([self.p3_boys_absent_poll], [self.kampala_district], self.term_range)
        self.assertEqual({self.kampala_school.id: 20}, school_results)

    def test_should_get_deployed_head_teachers(self):
        result = get_deployed_head_Teachers(EmisReporter.objects.all(), [self.kampala_district])
        self.assertEqual(2, result)

    def test_get_deployed_head_teachers_by_school(self):
        result = get_deployed_head_Teachers_by_school([self.kampala_school], [self.kampala_district])
        self.assertEqual(2, result)

    def test_get_count_deployed_head_teachers_by_location(self):
        result = get_count_deployed_head_teachers_by_location(EmisReporter.objects.all())
        self.assertEqual({self.kampala_district.id: 2}, result)

    def test_get_count_deployed_head_teachers_by_school(self):
        result = get_count_deployed_head_teachers_by_school(EmisReporter.objects.all())
        self.assertEqual({self.kampala_school.id: 2}, result)

    def test_get_count_gender_deployed_head_teachers_by_location(self):
        male_result = get_count_gender_deployed_head_teachers_by_location(EmisReporter.objects.all(), 'M')
        female_result = get_count_gender_deployed_head_teachers_by_location(EmisReporter.objects.all(), 'F')
        self.assertEqual({self.kampala_district.id: 2}, male_result)
        self.assertEqual({}, female_result)

    def test_get_count_for_yes_no_response_by_location(self):
        params = {
            "description": "A response value for a Poll with expected text responses",
            "datatype": "text",
            "enum_group": None,
            "required": False,
            "type": None,
            "slug": "poll_text_value",
            "name": "Text"
        }
        Attribute.objects.get_or_create(**params)

        schedule_script_now(self.smc_group.name, slug=self.head_teacher_weekly_script.slug)
        check_progress(self.head_teacher_weekly_script)
        fake_incoming("yes", self.emis_reporter3)

        yes, no = get_count_for_yes_no_response_by_location([self.head_teacher_monitoring_poll], [self.kampala_district], self.term_range)
        self.assertEqual({self.kampala_district.id : 1}, yes)
        self.assertEqual({}, no)

    def test_get_count_for_yes_no_response_by_school(self):
        params = {
            "description": "A response value for a Poll with expected text responses",
            "datatype": "text",
            "enum_group": None,
            "required": False,
            "type": None,
            "slug": "poll_text_value",
            "name": "Text"
        }
        Attribute.objects.get_or_create(**params)

        schedule_script_now(self.smc_group.name, slug=self.head_teacher_weekly_script.slug)
        check_progress(self.head_teacher_weekly_script)
        fake_incoming("yes", self.emis_reporter3)

        yes, no = get_count_for_yes_no_response_by_school([self.head_teacher_monitoring_poll], [self.kampala_district], self.term_range)
        self.assertEqual({self.kampala_school.id : 1}, yes)
        self.assertEqual({}, no)


    def test_gendered_text_responses(self):
        params = {
            "description": "A response value for a Poll with expected text responses",
            "datatype": "text",
            "enum_group": None,
            "required": False,
            "type": None,
            "slug": "poll_text_value",
            "name": "Text"
        }
        Attribute.objects.get_or_create(**params)

        schedule_script_now(self.smc_group.name, slug=self.head_teacher_weekly_script.slug)
        check_progress(self.head_teacher_weekly_script)
        fake_incoming("yes", self.emis_reporter3)

        male_yes_result = gendered_text_responses(self.term_range, [self.kampala_district], ['Yes', 'YES', 'yes'], 'M')
        male_no_result = gendered_text_responses(self.term_range, [self.kampala_district], ['No', 'NO', 'no'], 'M')
        female_yes_result = gendered_text_responses(self.term_range, [self.kampala_district], ['Yes', 'YES', 'yes'], 'F')
        female_no_result = gendered_text_responses(self.term_range, [self.kampala_district],  ['No', 'NO', 'no'], 'F')

        self.assertEqual(1, male_yes_result)
        self.assertEqual(0, male_no_result)
        self.assertEqual(0, female_yes_result)
        self.assertEqual(0, female_no_result)


    def test_get_aggregated_report_data_single_indicator(self):
        schedule_script_now(self.head_teacher_group.name, slug=self.head_teachers_termly_script.slug)
        check_progress(self.head_teachers_termly_script)
        fake_incoming("10 boys", self.emis_reporter1)
        check_progress(self.head_teachers_termly_script)
        fake_incoming("5 girls", self.emis_reporter1)
        schedule_script_now(self.head_teacher_group.name, slug=self.teachers_weekly_script.slug)

        check_progress(self.teachers_weekly_script)
        fake_incoming("8 boys", self.emis_reporter1)
        check_progress(self.teachers_weekly_script)
        fake_incoming("1 girls", self.emis_reporter1)

        config_list = get_polls_for_keyword('P3Boys')
        collective_result, chart_results_model, school_percent,tooltip = \
            get_aggregated_report_data_single_indicator([self.kampala_district], [self.term_range], config_list)

        self.assertEqual(20.0, collective_result['P3 Boys'][0].values()[0])

        config_list = get_polls_for_keyword('P3Girls')
        collective_result, chart_results_model, school_percent,tooltip = get_aggregated_report_data_single_indicator([self.kampala_district], [self.term_range], config_list)

        self.assertEqual(80.0, collective_result['P3 Girls'][0].values()[0])


    def test_aggregated_report_has_school_id(self):
        schedule_script_now(self.head_teacher_group.name, slug=self.head_teachers_termly_script.slug)
        check_progress(self.head_teachers_termly_script)
        fake_incoming("10 boys", self.emis_reporter1)

        config_list = get_polls_for_keyword('all')

        collective_result, chart_results_model, school_percent,tooltip = \
            get_aggregated_report_for_district([self.kampala_district], [self.term_range], config_list)

        self.assertEqual(self.kampala_school_lubaga.id, collective_result['UMHS Lubaga']['id'])


    def tearDown(self):
        Message.objects.all().delete()
        ScriptProgress.objects.all().delete()
        ScriptStep.objects.all().delete()
        ScriptSession.objects.all().delete()
        Script.objects.all().delete()
        Poll.objects.all().delete()
        EmisReporter.objects.all().delete()
        Location.objects.all().delete()
        LocationType.objects.all().delete()
        School.objects.all().delete()
        User.objects.all().delete()
        Group.objects.all().delete()
