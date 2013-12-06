from __future__ import division
from education.models import *
from poll.models import Poll
from .reports import *
from education.results import NumericResponsesFor
from education.absenteeism_view_helper import *

def get_aggregated_report_for_district(locations, time_range, config_list):
    collective_result = {}
    school_with_no_zero_by_indicator = {}
    enrollment_by_indicator = {}
    attendance_by_indicator = {}

    # Get term range from settings file (config file)
    term_range = [getattr(settings, 'SCHOOL_TERM_START'), getattr(settings, 'SCHOOL_TERM_END')]
    indicator_list = ['P3 Pupils', 'P6 Pupils', 'Teachers']
    # Initialize chart data and school percent List / dict holder
    for indicator in indicator_list:
        enrollment_by_indicator[indicator] = 0
        attendance_by_indicator[indicator] = []
        school_with_no_zero_by_indicator[indicator] = 0

    enrollment_by_indicator['Head Teachers'] = 0
    attendance_by_indicator['Head Teachers'] = []
    school_with_no_zero_by_indicator['Head Teachers'] = 0

    # update attendance by indicator with current date ranges (enable present computation along date x-axis)
    for _date in time_range:
        for v in attendance_by_indicator.values():
            v.append({'week': _date, 'present': 0, 'enrollment': 0, 'percent': 0})

    schoolSource = School.objects.filter(location__in=locations)
    for school in schoolSource:
        has_enrollment = False
        config_set_result = {}
        for config in config_list:
            if config.get('collective_dict_key') in indicator_list:
                enrollment_polls = Poll.objects.filter(name__in=[config.get('enrollment_poll')[0]])
                attendance_polls = Poll.objects.filter(name__in=[config.get('attendance_poll')[0]])
                enroll_data = get_numeric_data_by_school(enrollment_polls[0],[school],term_range)
                enrollment_by_indicator[config.get('collective_dict_key')] += sum(enroll_data)
                enroll_indicator_total = sum(enroll_data)
                week_count = 0
                weekly_results = []
                for week in time_range:
                    week_count += 1
                    attend_week_total = sum(get_numeric_data_by_school(attendance_polls[0], [school], week))
                    week_percent = compute_absent_values(attend_week_total, enroll_indicator_total)
                    weekly_results.append(week_percent)

                    if not is_empty(enroll_data):
                        for k, v in attendance_by_indicator.items():
                            if k == config.get('collective_dict_key'):
                                for val in v:
                                    if val['week'] == week:
                                        val['percent'] = val['percent'] + week_percent
                                        val['present'] = val['present'] + attend_week_total
                                        val['enrollment'] = enrollment_by_indicator[config.get('collective_dict_key')]

                if not is_empty(enroll_data):
                    has_enrollment = True
                    school_with_no_zero_by_indicator[config.get('collective_dict_key')] +=1
                    config_set_result[config.get('collective_dict_key')] = round(sum(weekly_results)/len(time_range),2)

            else: # Head teachers
                deployedHeadTeachers = get_deployed_head_Teachers_by_school([school],locations)
                enrollment_by_indicator[config.get('collective_dict_key')] += deployedHeadTeachers
                attendance_polls = Poll.objects.filter(name__in=['edtrac_head_teachers_attendance'])
                weekly_present = []
                weekly_percent = []
                for week in time_range:
                    present, absent = get_count_for_yes_no_by_school(attendance_polls,[school], week)
                    week_percent = compute_absent_values(present, deployedHeadTeachers)
                    weekly_present.append(present)
                    weekly_percent.append(week_percent)

                    if deployedHeadTeachers == 1:
                        for k, v in attendance_by_indicator.items():
                            if k == config.get('collective_dict_key'):
                                for val in v:
                                    if val['week'] == week:
                                        val['percent'] = val['percent'] + week_percent
                                        val['present'] = val['present'] + attend_week_total
                                        val['enrollment'] = enrollment_by_indicator[config.get('collective_dict_key')]


                if deployedHeadTeachers == 1:
                    school_with_no_zero_by_indicator[config.get('collective_dict_key')] += 1
                    has_enrollment = True
                    percent_absent = compute_absent_values(sum(weekly_present) / len(time_range), deployedHeadTeachers)
                    config_set_result[config.get('collective_dict_key')] = round(percent_absent, 2)

        if has_enrollment:
            collective_result[school.name] = config_set_result

    time_data_model = []
    school_data = {}

    for k,v in school_with_no_zero_by_indicator.items():
        school_data[k] = round((v*100)/len(schoolSource),2)

    # clean up collective_dict
    indicator_list = ['P3 Pupils', 'P6 Pupils', 'Teachers','Head Teachers']
    for k,v in collective_result.items():
        for item in indicator_list:
            v.setdefault(item,'--')

    # model percentage
    for key, entry in attendance_by_indicator.items():
        data = []
        for item in entry:
            percent = round(compute_absent_values(item['present'], item['enrollment']), 2)
            data.append(percent)
        time_data_model.append({'name': key, 'data': data})

    chart_results_model = time_data_model

    return collective_result, chart_results_model, school_data, []


def get_aggregated_report_data(locations, time_range, config_list):
    collective_result = {}
    school_report = []
    enrollment_by_indicator = {}
    attendance_by_indicator = {}

    # Get term range from settings file (config file)
    term_range = [getattr(settings, 'SCHOOL_TERM_START'), getattr(settings, 'SCHOOL_TERM_END')]

    headteachersSource = EmisReporter.objects.filter(reporting_location__in=locations, groups__name="Head Teachers").exclude(schools=None).select_related()
    schoolSource = School.objects.filter(location__in=locations).select_related()
    indicator_list = ['P3 Pupils', 'P6 Pupils', 'Teachers']
    schools_total = len(schoolSource)
    # Initialize chart data and school percent List / dict holder
    for indicator in indicator_list:
        school_report.append({indicator: [0] * len(time_range)})
        enrollment_by_indicator[indicator] = 0
        attendance_by_indicator[indicator] = []

    school_report.append({'Head Teachers': [0] * len(time_range)})
    enrollment_by_indicator['Head Teachers'] = 0
    attendance_by_indicator['Head Teachers'] = []

    # update attendance by indicator with current date ranges (enable present computation along date x-axis)
    for _date in time_range:
        for v in attendance_by_indicator.values():
            v.append({'week': _date, 'present': 0, 'enrollment': 0, 'percent': 0})

    for location in locations:
        config_set_result = {}
        has_enrollment = False
        # get school in current location
        schools_in_location = schoolSource.filter(location__in=[location])

        for config in config_list:
            if config.get('collective_dict_key') in indicator_list:
                enrollment_polls = Poll.objects.filter(name__in=[config.get('enrollment_poll')[0]])
                attendance_polls = Poll.objects.filter(name__in=[config.get('attendance_poll')[0]])
                # get both enroll list and schools that responded
                enroll_indicator_total, responsive_schools = get_numeric_enrollment_data(enrollment_polls[0],[location],term_range)
                has_enrollment = enroll_indicator_total > 0
                enrollment_by_indicator[config.get('collective_dict_key')] += enroll_indicator_total

                absenteeism_percent = 0
                week_count = 0
                weekly_results = []
                weekly_results_log = []
                weekly_school_count = []

                for week in time_range:
                    week_count += 1
                    # get attendance total for week by indicator from config file
                    attend_week_total = sum(get_numeric_data_by_school(attendance_polls[0], responsive_schools, week))
                    # get schools that Responded
                    schools_that_responded = len(get_numeric_data_by_school(attendance_polls[0], schools_in_location, week))
                    week_percent = compute_absent_values(attend_week_total, enroll_indicator_total)
                    absenteeism_percent += week_percent
                    weekly_school_count.append(schools_that_responded)
                    weekly_results.append(week_percent)
                    weekly_results_log.append(week_percent)
                    weekly_results_log.append('P' + str(attend_week_total))
                    weekly_results_log.append('E' + str(enroll_indicator_total))


                    # update attendance by indicator collection with values per week
                    for k, v in attendance_by_indicator.items():
                        if k == config.get('collective_dict_key'):
                            for val in v:
                                if val['week'] == week:
                                    val['percent'] = val['percent'] + week_percent
                                    val['present'] = val['present'] + attend_week_total
                                    val['enrollment'] = enrollment_by_indicator[config.get('collective_dict_key')]

                # update school reporting summary collection
                for item in school_report:
                    for k, v in item.items():
                        if k == config.get('collective_dict_key'):
                            item[k] = [sum(a) for a in zip(*[v, weekly_school_count])]

                # adds average percentage to dict_key
                config_set_result[config.get('collective_dict_key')] = round(absenteeism_percent / len(time_range),2)

            else: # used to compute head teachers absenteeism
                deployedHeadTeachers = get_deployed_head_Teachers(headteachersSource, [location])
                enrollment_by_indicator[config.get('collective_dict_key')] += deployedHeadTeachers
                attendance_polls = Poll.objects.filter(name__in=['edtrac_head_teachers_attendance'])
                weekly_present = []
                weekly_percent = []
                weekly_school_count = []
                for week in time_range:
                    present, absent = get_count_for_yes_no_response(attendance_polls, [location], week)
                    schools_that_responded = len(
                        get_numeric_data_by_school(attendance_polls[0], schools_in_location, week))
                    week_percent = compute_absent_values(present, deployedHeadTeachers)
                    weekly_present.append(present)
                    weekly_percent.append(week_percent)
                    weekly_school_count.append(schools_that_responded)
                    # update attendance by indicator collection with values per week
                    for k, v in attendance_by_indicator.items():
                        if k == config.get('collective_dict_key'):
                            for val in v:
                                if val['week'] == week:
                                    val['percent'] = val['percent'] + week_percent
                                    val['present'] = val['present'] + present
                                    val['enrollment'] = enrollment_by_indicator[config.get('collective_dict_key')]

                percent_absent = compute_absent_values(sum(weekly_present) / len(time_range), deployedHeadTeachers)
                config_set_result[config.get('collective_dict_key')] = round(percent_absent, 2)
                for item in school_report:
                    for k, v in item.items():
                        if k == config.get('collective_dict_key'):
                            item[k] = [sum(a) for a in zip(*[v, weekly_school_count])]

        if has_enrollment:
            collective_result[location.name] = config_set_result

    #absenteeism computation model : problem : hides some facts a long each location and computes at global count across all locations
    # get sum of present values for all locations, sum of  enrollment values for all locations, all accross each indicator
    time_data_model = []
    for key, entry in attendance_by_indicator.items():
        data = [round(compute_absent_values(item['present'], item['enrollment']), 2) for item in entry]
        time_data_model.append({'name': key, 'data': data})

    # get school response average
    school_data = {}
    for item in school_report:
        for k, v in item.items():
            school_data[k] = round(((sum(v) / len(time_range)) / schools_total) * 100, 2)

    chart_results_model = time_data_model

    return collective_result, chart_results_model, school_data, []


def get_aggregated_report_data_single_indicator(locations, time_range, config_list):
    collective_result = {}
    location_with_no_zero_result = []
    avg_percent_by_location = []
    avg_school_responses = []
    aggregated_enrollment = []
    aggregated_attendance = []

    # Get term range from settings file (config file)
    term_range = [getattr(settings, 'SCHOOL_TERM_START'), getattr(settings, 'SCHOOL_TERM_END')]
    headteachersSource = EmisReporter.objects.filter(reporting_location__in=locations,groups__name="Head Teachers").exclude(schools=None).select_related()
    schoolSource = School.objects.filter(location__in=locations).select_related()

    for location in locations:
        # get school in current location
        schools_in_location = schoolSource.filter(location__in=[location])
        weekly_percent_results = []
        weekly_present_result = []
        weekly_school_responses = []

        if config_list[0].get('collective_dict_key') not in  ['Male Head Teachers', 'Female Head Teachers', 'Head Teachers']:
            enrollment_polls = Poll.objects.filter(name__in=config_list[0].get('enrollment_poll'))
            attendance_polls = Poll.objects.filter(name__in=config_list[0].get('attendance_poll'))
            enroll_indicator_total, responsive_schools = get_numeric_enrollment_data(enrollment_polls[0],[location],term_range)
            for week in time_range:
                # get attendance total for week by indicator from config file
                attend_week_total = sum(get_numeric_data_by_school(attendance_polls[0],responsive_schools,week))
                weekly_present_result.append(attend_week_total)
                # get schools that Responded
                # suspect (can be replaced by count of response values on weekly attendance above)
                schools_that_responded = len(get_numeric_data_by_school(attendance_polls[0], schools_in_location, week))
                week_percent = compute_absent_values(attend_week_total, enroll_indicator_total)
                weekly_percent_results.append(week_percent)
                weekly_school_responses.append(schools_that_responded)
            if sum(weekly_percent_results) != 0:
                aggregated_enrollment.append(enroll_indicator_total)
                if is_empty(aggregated_attendance):
                    aggregated_attendance = weekly_present_result
                else:
                    aggregated_attendance = [sum(z) for z in zip(*[aggregated_attendance,weekly_present_result])]
                location_with_no_zero_result.append(location)
                avg_percent_by_location.append({location.name: round(sum(weekly_percent_results) / len(time_range),2)})

            avg_school_responses.append(sum(weekly_school_responses) / len(time_range))
        elif config_list[0].get('collective_dict_key') in ['Male Head Teachers', 'Female Head Teachers']:
            for week in time_range:
                present = gendered_text_responses(week, [location], ['Yes', 'YES', 'yes'], config_list[0].get('gender'))
                absent = gendered_text_responses(week, [location], ['No', 'NO', 'no'], config_list[0].get('gender'))
                total_gender_teachers = present + absent

                schools_that_responded = total_gender_teachers
                week_percent = compute_absent_values(present, total_gender_teachers)
                weekly_percent_results.append(week_percent)
                weekly_present_result.append(present)
                weekly_school_responses.append(schools_that_responded)
            if sum(weekly_percent_results) != 0: # eliminate districts that have nothing to present
                location_with_no_zero_result.append(location)
                avg_percent_by_location.append({location.name: round(sum(weekly_percent_results) / len(time_range),2)})
            avg_school_responses.append(sum(weekly_school_responses) / len(time_range))

        else: # compute head teacher absenteeism
            deployedHeadTeachers = get_deployed_head_Teachers(headteachersSource, [location])
            attendance_polls = Poll.objects.filter(name__in=['edtrac_head_teachers_attendance'])

            for week in time_range:
                present, absent = get_count_for_yes_no_response(attendance_polls, [location], week)
                schools_that_responded = len(get_numeric_data_by_school(attendance_polls[0], schools_in_location, week))
                week_percent = compute_absent_values(present, deployedHeadTeachers)
                weekly_percent_results.append(week_percent)
                weekly_present_result.append(present)
                weekly_school_responses.append(schools_that_responded)
            if sum(weekly_percent_results) != 0: # eliminate districts that have nothing to present
                location_with_no_zero_result.append(location)
                avg_percent_by_location.append({location.name: round(sum(weekly_percent_results) / len(time_range),2)})
            avg_school_responses.append(sum(weekly_school_responses) / len(time_range))

    collective_result[config_list[0].get('collective_dict_key')] = avg_percent_by_location

    # percentage of schools that responded : add up weekly response average by selected locations and divide by total number of schools
    school_percent = round((sum(avg_school_responses) / len(schoolSource)) * 100, 2)

    chart_results_model = time_data_model(aggregated_enrollment, aggregated_attendance, config_list)

    return collective_result, chart_results_model, school_percent, {}

# Model : get percentage for aggregated results i.e. total enrollment, total attendance by week
def time_data_model(aggregated_enrollment, aggregated_attendance, config_list):
    output = [compute_absent_values(a,sum(aggregated_enrollment)) for a in aggregated_attendance]
    return [{'name' :config_list[0].get('collective_dict_key'), 'data' : output }]


def compute_absenteeism_summary(indicator, locations, get_time=datetime.datetime.now):
    date_weeks = get_week_date(depth=2, get_time=get_time)
    term_range = [getattr(settings, 'SCHOOL_TERM_START'), getattr(settings, 'SCHOOL_TERM_END')]
    current_week_date_range = date_weeks[0]
    previous_week_date_range = date_weeks[1]

    config_list = get_polls_for_keyword(indicator)
    poll_enrollment = Poll.objects.get(name=config_list[0].get('enrollment_poll')[0])
    poll_attendance = Poll.objects.get(name=config_list[0].get('attendance_poll')[0])

    enrollment_total = get_numeric_data(poll_enrollment, locations, term_range)
    current_week_present_total = get_numeric_data(poll_attendance, locations, current_week_date_range)
    previous_week_present_total= get_numeric_data(poll_attendance, locations, previous_week_date_range)

    absent_current_week = round(compute_absent_values(current_week_present_total, enrollment_total), 2)
    absent_previous_week = round(compute_absent_values(previous_week_present_total, enrollment_total), 2)

    return (absent_current_week, absent_previous_week)


def get_count_for_yes_no_response(polls, locations, time_range):
    yes_result =  Response.objects.filter(poll__in = polls,
                                      has_errors = False,
                                      message__direction = 'I',
                                      date__range = time_range,
                                      eav_values__value_text__in = ['Yes', 'YES', 'yes'],
                                      contact__reporting_location__in = locations) \
                              .values('contact__reporting_location__id').count()
    no_result =  Response.objects.filter(poll__in = polls,
                                      has_errors = False,
                                      message__direction = 'I',
                                      date__range = time_range,
                                      eav_values__value_text__in = ['No', 'NO', 'no'],
                                      contact__reporting_location__in = locations) \
                              .values('contact__reporting_location__id').count()
    if not yes_result:
        yes_result = 0
    if not no_result:
        no_result = 0

    return yes_result, no_result


def get_count_for_yes_no_by_school(polls, School, time_range):
    yes_result =  Response.objects.filter(poll__in = polls,
                                      has_errors = False,
                                      message__direction = 'I',
                                      date__range = time_range,
                                      eav_values__value_text__in = ['Yes', 'YES', 'yes'],
                                      contact__emisreporter__schools__in=School,) \
                              .values('contact__reporting_location__id').count()
    no_result =  Response.objects.filter(poll__in = polls,
                                      has_errors = False,
                                      message__direction = 'I',
                                      date__range = time_range,
                                      eav_values__value_text__in = ['No', 'NO', 'no'],
                                      contact__emisreporter__schools__in=School,) \
                              .values('contact__reporting_location__id').count()
    if not yes_result:
        yes_result = 0
    if not no_result:
        no_result = 0

    return yes_result, no_result


#  Function called to populate in-memory Data, reduces on number of db queries per request.
def get_record_collection(locations, time_range):
    try:
        return Response.objects.filter(date__range = time_range,
                                       has_errors = False,
                                       contact__reporting_location__in = locations,
                                       message__direction = 'I').select_related()
    except:
        return [] # Log database errors (or lookup db error exceptions and be specific on exception)

def get_deployed_head_Teachers_by_school(school, locations):
    heads = EmisReporter.objects.filter(reporting_location__in = locations,
                                        schools__in = school,
                                        groups__name = 'SMC')
    return heads.distinct().count()


def get_deployed_head_Teachers(dataSource, locations):
    return get_deployed_head_Teachers_by_school(dataSource.values_list('schools', flat=True), locations)

def get_numeric_data(poll, locations, time_range):
    return NumericResponsesFor(poll).forDateRange(time_range).forLocations(locations).total()

def get_numeric_data_for_location(poll, locations, time_range):
    return NumericResponsesFor(poll).forDateRange(time_range).forLocations(locations).groupByLocation()

def get_numeric_data_all_locations(poll, time_range):
    return NumericResponsesFor(poll).forDateRange(time_range).groupByLocation()

def get_numeric_enrollment_data(poll, locations, time_range):
    results = NumericResponsesFor(poll).forDateRange(time_range) \
                                       .forLocations(locations) \
                                       .excludeZeros() \
                                       .groupBySchools()

    return sum(results.values()), results.keys()

def get_numeric_data_by_school(poll, schools, time_range):
    return NumericResponsesFor(poll).forDateRange(time_range) \
                                    .forSchools(schools) \
                                    .groupBySchools() \
                                    .values()

def compute_absent_values(present, enrollment):
    if enrollment == 0:
        return 0
    else:
        return round(((enrollment - present) * 100 / enrollment), 2)

def gendered_text_responses(date_weeks, locations, options, gender):
    poll = Poll.objects.get(name='edtrac_head_teachers_attendance')
    gendered_schools = EmisReporter.objects.filter(reporting_location__in = locations,
                                                   gender = gender,
                                                   groups__name = "Head Teachers") \
                                           .exclude(schools = None) \
                                           .values('reporting_location__id')

    result =  Response.objects.filter(poll = poll,
                                      has_errors = False,
                                      message__direction = 'I',
                                      date__range = date_weeks,
                                      eav_values__value_text__in = options,
                                      contact__reporting_location__id__in = gendered_schools) \
                              .values('contact__reporting_location__id').count()
    return result or 0