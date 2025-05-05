import logging

from django.contrib.auth import logout as auth_logout
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse
from urllib.parse import urlencode

logger = logging.getLogger('')

def login(request: HttpRequest) -> HttpResponse:
    if request.GET:
        next = request.GET.get('next', None)
    else:
        next = None

    login_url = f'https://{ get_current_site(request) }{reverse("oidc_authentication_init")}'
    if next:
        parameters = urlencode({'next': next})
        redirect_url = f'{login_url}?{parameters}'
    else:
        redirect_url = login_url
    logger.debug(f'redirecting to: {redirect_url}')

    return HttpResponseRedirect(redirect_url)


def logout(request: HttpRequest) -> HttpResponse:
    auth_logout(request)
    return HttpResponseRedirect(reverse('helpdesk:kb_index'))
