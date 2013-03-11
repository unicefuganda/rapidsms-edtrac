# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
from django.contrib.auth.models import User
from django.http import HttpRequest
from education.models import Role, School, UserProfile, EmisReporter
from poll.models import Poll
from rapidsms.contrib.locations.models import LocationType, Location, Point
from rapidsms.models import Backend


def create_user_with_group(username,group=None, location=None):
    user = User.objects.create(username=username)
    user.set_password('password')
    if group is not None:
        user.groups.add(group)
        if location is not None:
            UserProfile.objects.create(name=username,location=location,role=group,user=user)
    user.save()
    return user

def create_group(group_name):
    return Role.objects.create(name=group_name)

def create_location(location_name,location_type, point=None, **kwargs):
    if point is not None:
        kwargs['point'] = Point.objects.create(**point)
    fields={
        "name":location_name,
        "type":location_type
    }
    fields.update(kwargs)
    return Location.objects.create(**fields)

def create_location_type(location_type):
    return LocationType.objects.create(name=location_type, slug=location_type)

def create_school(name,location):
    return School.objects.create(name=name,location=location)

def create_emis_reporters(name, reporting_location, school, identity, group):
    reporter = EmisReporter.objects.create(name=name, reporting_location=reporting_location)
    reporter.schools.add(school)
    reporter.groups.add(group)
    backend, created = Backend.objects.get_or_create(name='fake_backend')
    reporter.connection_set.create(identity=identity, backend=backend)
    reporter.save()
    return reporter

def create_poll(name,question,user,contacts):
    params = {
        "default_response": "",
        "name": name,
        "question": question,
        "user": user,
        "type": Poll.TYPE_TEXT,
        "response_type": Poll.RESPONSE_TYPE_ALL
    }
    poll = Poll.objects.create(**params)
    poll.add_yesno_categories()
    poll.contacts.add(*contacts)
    poll.save()
    poll.start()
    return poll

def create_view(class_name,user, poll, group):
    view = class_name(poll_name=poll.name, restrict_group=group.name)
    request = HttpRequest()
    request.user = user
    view.request = request
    return view