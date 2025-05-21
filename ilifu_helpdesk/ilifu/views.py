from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import render
from django.utils.translation import gettext as _

from helpdesk import settings as helpdesk_settings
from helpdesk.decorators import (
    helpdesk_staff_member_required,
)
from helpdesk.query import get_query_class
from helpdesk.models import (
    Ticket,
)
from helpdesk.user import HelpdeskUser
from helpdesk.views.staff import calc_basic_ticket_stats


User = get_user_model()
Query = get_query_class()

if helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE:
    # treat 'normal' users like 'staff'
    staff_member_required = user_passes_test(
        lambda u: u.is_authenticated and u.is_active
    )
else:
    staff_member_required = user_passes_test(
        lambda u: u.is_authenticated and u.is_active and u.is_staff
    )


# Create your views here.

@helpdesk_staff_member_required
def dashboard(request):
    """
    A quick summary overview for users: A list of their own tickets, a table
    showing ticket counts by queue/status, and a list of unassigned tickets
    with options for them to 'Take' ownership of said tickets.
    """
    # user settings num tickets per page
    if request.user.is_authenticated and hasattr(request.user, "usersettings_helpdesk"):
        tickets_per_page = request.user.usersettings_helpdesk.tickets_per_page
    else:
        tickets_per_page = 25

    # page vars for the three ticket tables
    user_tickets_page = request.GET.get(_("ut_page"), 1)
    user_tickets_closed_resolved_page = request.GET.get(_("utcr_page"), 1)
    all_tickets_reported_by_current_user_page = request.GET.get(_("atrbcu_page"), 1)
    recent_activity_page = request.GET.get(_('ra_page'), 1)

    huser = HelpdeskUser(request.user)
    active_tickets = Ticket.objects.select_related("queue").exclude(
        status__in=[
            Ticket.CLOSED_STATUS,
            Ticket.RESOLVED_STATUS,
            Ticket.DUPLICATE_STATUS,
        ],
    )

    # open & reopened tickets, assigned to current user
    tickets = active_tickets.filter(
        assigned_to=request.user,
    ).order_by('-modified')

    # closed & resolved tickets, assigned to current user
    tickets_closed_resolved = Ticket.objects.select_related("queue").filter(
        assigned_to=request.user,
        status__in=[
            Ticket.CLOSED_STATUS,
            Ticket.RESOLVED_STATUS,
            Ticket.DUPLICATE_STATUS,
        ],
    ).order_by('-modified')

    recent_activity_tickets = Ticket.objects.all().select_related("queue").order_by('-modified')

    user_queues = huser.get_queues()

    unassigned_tickets = active_tickets.filter(
        assigned_to__isnull=True, queue__in=user_queues
    )
    kbitems = None
    # Teams mode uses assignment via knowledge base items so exclude tickets assigned to KB items
    if helpdesk_settings.HELPDESK_TEAMS_MODE_ENABLED:
        unassigned_tickets = unassigned_tickets.filter(kbitem__isnull=True)
        kbitems = huser.get_assigned_kb_items()

    # all tickets, reported by current user
    all_tickets_reported_by_current_user = ""
    email_current_user = request.user.email
    if email_current_user:
        all_tickets_reported_by_current_user = (
            Ticket.objects.select_related("queue")
            .filter(
                submitter_email=email_current_user,
            )
            .order_by("status")
        )

    tickets_in_queues = Ticket.objects.filter(
        queue__in=user_queues,
    )
    basic_ticket_stats = calc_basic_ticket_stats(tickets_in_queues)

    # The following query builds a grid of queues & ticket statuses,
    # to be displayed to the user. EG:
    #          Open  Resolved
    # Queue 1    10     4
    # Queue 2     4    12
    # code never used (and prone to sql injections)
    # queues = HelpdeskUser(request.user).get_queues().values_list('id', flat=True)
    # from_clause = """FROM    helpdesk_ticket t,
    #                 helpdesk_queue q"""
    # if queues:
    #     where_clause = """WHERE   q.id = t.queue_id AND
    #                     q.id IN (%s)""" % (",".join(("%d" % pk for pk in queues)))
    # else:
    #     where_clause = """WHERE   q.id = t.queue_id"""

    # get user assigned tickets page
    paginator = Paginator(tickets, tickets_per_page)
    try:
        tickets = paginator.page(user_tickets_page)
    except PageNotAnInteger:
        tickets = paginator.page(1)
    except EmptyPage:
        tickets = paginator.page(paginator.num_pages)

    # get user completed tickets page
    paginator = Paginator(tickets_closed_resolved, tickets_per_page)
    try:
        tickets_closed_resolved = paginator.page(user_tickets_closed_resolved_page)
    except PageNotAnInteger:
        tickets_closed_resolved = paginator.page(1)
    except EmptyPage:
        tickets_closed_resolved = paginator.page(paginator.num_pages)

    # get user submitted tickets page
    paginator = Paginator(all_tickets_reported_by_current_user, tickets_per_page)
    try:
        all_tickets_reported_by_current_user = paginator.page(
            all_tickets_reported_by_current_user_page
        )
    except PageNotAnInteger:
        all_tickets_reported_by_current_user = paginator.page(1)
    except EmptyPage:
        all_tickets_reported_by_current_user = paginator.page(paginator.num_pages)

    paginator = Paginator(recent_activity_tickets, tickets_per_page)
    try:
        recent_activity_tickets = paginator.page(recent_activity_page)
    except PageNotAnInteger:
        recent_activity_tickets = paginator.page(1)
    except EmptyPage:
        recent_activity_tickets = paginator.page(paginator.num_pages)


    return render(
        request,
        "helpdesk/dashboard.html",
        {
            "user_tickets": tickets,
            "user_tickets_closed_resolved": tickets_closed_resolved,
            "unassigned_tickets": unassigned_tickets,
            "kbitems": kbitems,
            "all_tickets_reported_by_current_user": all_tickets_reported_by_current_user,
            "basic_ticket_stats": basic_ticket_stats,
            "recent_activity_tickets": recent_activity_tickets,
        },
    )


dashboard = staff_member_required(dashboard)
