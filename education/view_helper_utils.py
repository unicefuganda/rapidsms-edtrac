from __future__ import division
import re
#from .forms import *
from education.models import *
from poll.models import Poll
from .reports import *
from education.absenteeism_view_helper import *


def get_aggregated_report_data(locations,time_range,config_list):
    collective_result = {}
    chart_data = []
    head_teacher_set = []
    tmp_data = []
    school_report = []
    schools_by_location = []
    high_chart_tooltip = []
    attendance_total = [] # used for logging present values extracted from incoming messages (don't delete)
    percent_by_indicator = {} # used for logging percent values extracted from incoming messages (don't delete)
    enrollment_by_indicator = {}
    attendance_by_indicator = {}

    # Get term range from settings file (config file)
    term_range=[getattr(settings, 'SCHOOL_TERM_START'), getattr(settings, 'SCHOOL_TERM_END')]

    headteachersSource = EmisReporter.objects.filter(reporting_location__in=locations, groups__name="Head Teachers").exclude(schools=None).select_related()
    schoolSource = School.objects.filter(location__in=locations).select_related()
    indicator_list = ['P3 Pupils','P6 Pupils','Teachers']
    schools_total = len(schoolSource)
     # Initialize chart data and school percent List / dict holder
    for indicator in indicator_list:
        chart_data.append({ indicator : [0]*len(time_range)})
        school_report.append({ indicator : [0]*len(time_range)})
        high_chart_tooltip.append({indicator : []})
        enrollment_by_indicator[indicator] = 0
        attendance_by_indicator[indicator] = []
        percent_by_indicator[indicator] = []

    chart_data.append({'Head Teachers' :[0]*len(time_range)})
    school_report.append({'Head Teachers' :[0]*len(time_range)})
    high_chart_tooltip.append({'Head Teachers' : []})
    enrollment_by_indicator['Head Teachers'] = 0
    attendance_by_indicator['Head Teachers'] = []

    # update tooltip list with current date ranges (high chart x - axis values)
    for _date in time_range:
        for tip in high_chart_tooltip:
            for k,v in tip.items():
                v.append({'date_range': _date, 'enrollment' : 0, 'present' : 0})

    # update attendance by indicator with current date ranges (enable present computation along date x-axis)
    for _date in time_range:
        for k,v in attendance_by_indicator.items():
            v.append({'week': _date,'present' : 0, 'enrollment' : 0,'percent' : 0 })

    for location in locations:
        absenteeism_percent = 0
        config_set_result = {}
        # get school in current location
        schools_in_location = schoolSource.filter(location__in=[location])

        schools_by_location.append({'location' : location,'school_count':len(schools_in_location)})
        for config in config_list:
            if config.get('collective_dict_key') in indicator_list:
                enrollment_polls = Poll.objects.filter(name__in=[config.get('enrollment_poll')[0]])
                attendance_polls = Poll.objects.filter(name__in=[config.get('attendance_poll')[0]])
                enroll_indicator_total = sum(get_numeric_data(enrollment_polls,[location],term_range))
                enrollment_by_indicator[config.get('collective_dict_key')] += enroll_indicator_total
                week_count = 0
                weekly_results = []
                weekly_results_log = []
                weekly_school_count = []

                for week in time_range:
                    week_count +=1
                    # get attendance total for week by indicator from config file
                    attend_week_total = sum(get_numeric_data(attendance_polls,[location],week))
                    attendance_total.append(attend_week_total)
                    # get schools that Responded
                    schools_that_responded = len(get_numeric_data_by_school(attendance_polls,schools_in_location,week))
                    week_percent = compute_absent_values(attend_week_total,enroll_indicator_total)
                    absenteeism_percent +=week_percent
                    weekly_school_count.append(schools_that_responded)
                    weekly_results.append(week_percent)
                    weekly_results_log.append(week_percent)
                    weekly_results_log.append('P'+str(attend_week_total))
                    weekly_results_log.append('E'+str(enroll_indicator_total))


                    # update attendance by indicator collection with values per week
                    for k,v in attendance_by_indicator.items():
                        if k == config.get('collective_dict_key'):
                            for val in v:
                                if val['week'] == week:
                                    val['percent'] = val['percent'] + week_percent
                                    val['present'] = val['present'] + attend_week_total
                                    val['enrollment'] = enrollment_by_indicator[config.get('collective_dict_key')]

                    # update tooltip collection with new values through interations
                    for tooltip in high_chart_tooltip:
                        for k,v in tooltip.items():
                            if k == config.get('collective_dict_key'):
                                for values in v:
                                    if values['date_range'] == week :
                                        values['present'] = values['present'] + attend_week_total
                                        values['enrollment'] = enrollment_by_indicator[config.get('collective_dict_key')]

                percent_by_indicator[config.get('collective_dict_key')].append(weekly_results_log)
                # update high chart data collection with new values through interation
                for item in chart_data:
                    for k,v in item.items():
                        if k == config.get('collective_dict_key'):
                            item[k] = [sum(a) for a in zip(*[v,weekly_results])]

                # update school reporting summary collection
                for item in school_report:
                    for k,v in item.items():
                        if k == config.get('collective_dict_key'):
                            item[k] = [sum(a) for a in zip(*[v,weekly_school_count])]

                config_set_result[config.get('collective_dict_key')] = round(absenteeism_percent/len(time_range),2) # adds average percentage to dict_key
                tmp_data.append({location.name :{'Indicator' :config.get('collective_dict_key'),'Schools' :weekly_school_count }})

            else: # used to compute head teachers absenteeism
                deployedHeadTeachers = get_deployed_head_Teachers(headteachersSource,[location])
                enrollment_by_indicator[config.get('collective_dict_key')] = deployedHeadTeachers
                attendance_polls = Poll.objects.filter(name__in=['edtrac_head_teachers_attendance'])
                weekly_present = []
                weekly_percent = []
                weekly_school_count = []
                for week in time_range:
                    present,absent = get_count_for_yes_no_response(attendance_polls,[location],week)
                    schools_that_responded = len(get_numeric_data_by_school(attendance_polls,schools_in_location,week))
                    week_percent = compute_absent_values(present,deployedHeadTeachers)
                    weekly_present.append(present)
                    weekly_percent.append(week_percent)
                    weekly_school_count.append(schools_that_responded)
                    # update attendance by indicator collection with values per week
                    for k,v in attendance_by_indicator.items():
                        if k == config.get('collective_dict_key'):
                            for val in v:
                                if val['week'] == week:
                                    val['percent'] = val['percent'] + week_percent
                                    val['present'] = val['present'] + present
                                    val['enrollment'] = enrollment_by_indicator[config.get('collective_dict_key')]
                    # update tooltip collection with new values through interations
                    for tooltip in high_chart_tooltip:
                        for k,v in tooltip.items():
                            if k == config.get('collective_dict_key'):
                                for values in v:
                                    if values['date_range'] == week :
                                        values['present'] = values['present'] + present
                                        values['enrollment'] = enrollment_by_indicator[config.get('collective_dict_key')]


                percent_absent = compute_absent_values(sum(weekly_present)/len(time_range),deployedHeadTeachers)
                head_teacher_set.append({'Location':location,'present':weekly_present,'deployed' :deployedHeadTeachers,'percent':percent_absent })
                config_set_result[config.get('collective_dict_key')] = round(percent_absent,2)
                for item in chart_data:
                    for k,v in item.items():
                        if k == 'Head Teachers':
                            item[k] = [sum(a) for a in zip(*[v,weekly_percent])]
                for item in school_report:
                    for k,v in item.items():
                        if k == config.get('collective_dict_key'):
                            item[k] = [sum(a) for a in zip(*[v,weekly_school_count])]


        collective_result[location.name] = config_set_result
    time_data_model1 = []
    school_data = {}
    tip_for_time_data1 = []

    # Absenteeism Computation Model 1 : problem : some locations return very high negative values, makes the dashboard look messy (but represent actual state of data)
    # get averages to display on chart (formula : divide the aggregated percent value along each week for each indicator in each location and divide by location count )
    for item in chart_data:
        for k,v in item.items():
            output = []
            for val in v:
                avg_percent = round(val/len(locations),2)
                output.append(avg_percent)
            time_data_model1.append({'name' : k, 'data' : output})



    #absenteeism computation model 2 : problem : hides some facts a long each location and computes at global count across all locations
    # get sum of present values for all locations, sum of  enrollment values for all locations, all accross each indicator
    time_data_model2 = []
    tip_for_time_data2 = []
    for key,entry in attendance_by_indicator.items():
        data = []
        tip = []
        for item in entry:
            percent = round(compute_absent_values(item['present'],item['enrollment']),2)
            tip.append({'enrollment':item['enrollment'],'present':item['present'],'percent' : percent})
            data.append(percent)
        time_data_model2.append({'name' : key, 'data' : data})
        tip_for_time_data2.append({'name' : key,'tooltip' : tip})

    # get school response average
    for item in school_report:
        for k,v in item.items():
            output = []
            for val in v:
                output.append(val)
                school_data[k] = round(((sum(output)/len(time_range))/schools_total)*100,2)

    return collective_result, time_data_model1, school_data, tip_for_time_data2


def compute_absenteeism_summary(indicator,locations):
    date_weeks = get_week_date(depth=2)
    term_range=[getattr(settings, 'SCHOOL_TERM_START'), getattr(settings, 'SCHOOL_TERM_END')]
    current_week_date_range = date_weeks[0]
    previous_week_date_range = date_weeks[1]
    enrollment_total = 0
    current_week_present_total = 0
    previous_week_present_total = 0
    present_by_time = []

    config_list = get_polls_for_keyword(indicator)
    poll_enrollment = Poll.objects.get(name=config_list[0].get('enrollment_poll')[0])
    poll_attendance = Poll.objects.get(name=config_list[0].get('attendance_poll')[0])

    results = get_numeric_data([poll_enrollment],locations,term_range)
    if not is_empty(results):
        enrollment_total = sum(results)

    results =  get_numeric_data([poll_attendance],locations,current_week_date_range)
    if not is_empty(results):
        current_week_present_total = sum(results)

    results = get_numeric_data([poll_attendance],locations,previous_week_date_range)
    if not is_empty(results):
        previous_week_present_total = sum(results)

    absent_current_week = round(compute_absent_values(current_week_present_total, enrollment_total),2)
    absent_previous_week = round(compute_absent_values(previous_week_present_total, enrollment_total),2)
    present_by_time.append(absent_current_week)
    present_by_time.append(absent_previous_week)

    return present_by_time


def get_digit_value_from_message_text(messge):
    digit_value = 0
    regex = re.compile(r"(-?\d+(\.\d+)?)")
     #split the text on number regex. if the msg is of form
     #'19'or '19 years' or '19years' or 'age19'or 'ugx34.56shs' it returns a list of length 4
    msg_parts = regex.split(messge)
    if len(msg_parts) == 4:
        digit_value = round(float(msg_parts[1]),3)
    return digit_value

def get_count_for_yes_no_response(polls,dataSource, locations=None, time_range=None):
    yes = 0
    no = 0
    if time_range:
        if locations:
                responses =  dataSource.filter(date__range=time_range,poll__in=polls,has_errors=False,contact__reporting_location__in=locations,message__direction='I')
                for response in responses:
                    if 'yes' in response.message.text.lower():
                        yes += 1
                    if 'no' in response.message.text.lower():
                        no +=1
    return yes, no



#  Function called to populate in-memory Data, reduces on number of db queries per request.
def get_record_collection(locations,time_range):
    results = []
    try:
        if time_range:
            if locations:
                results = Response.objects.filter(date__range=time_range,has_errors=False,contact__reporting_location__in=locations,message__direction='I').select_related()
    except:
        pass # Log database errors (or lookup db error exceptions and be specific on exception)
    return results

def get_deployed_head_Teachers(dataSource, locations=None):
    result = 0
    if locations:
        deployedHeadTeachers = EmisReporter.objects.filter(reporting_location__in=locations,
                                                           schools__in=dataSource.values_list('schools', flat=True),
                                                           groups__name='SMC').distinct()
        result = len(deployedHeadTeachers)
    return result


def get_numeric_data(polls, locations=None, time_range=None):
    results = []
    if time_range:
        if locations:
                responses = Response.objects.filter(date__range=time_range,poll__in=polls,has_errors=False,contact__reporting_location__in=locations,message__direction='I')
                for response in responses:
                    results.append(get_digit_value_from_message_text(response.message.text))
    return results

def get_numeric_data_by_school(polls, schools=None, time_range=None):
    results = []
    if time_range:
        if schools:
                responses = Response.objects.filter(date__range=time_range,poll__in=polls,has_errors=False,contact__emisreporter__schools__in= schools,message__direction='I')
                for response in responses:
                    results.append(get_digit_value_from_message_text(response.message.text))

    return results


def compute_absent_values(present,enrollment):
    try:
        if present != 0:
            return  round(((enrollment - present)*100 / enrollment),2)
        elif present==0 and enrollment > 0:
            return 100
        else:
            return 0
    except ZeroDivisionError:
        return 0

