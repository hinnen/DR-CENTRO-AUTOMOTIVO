from django.conf import settings


def workshop(request):
    return {"workshop_name": settings.WORKSHOP_NAME}
