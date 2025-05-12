from email.utils import getaddresses
import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.utils.html import escape, linebreaks
from django.utils.translation import gettext as _
from helpdesk import settings as helpdesk_settings
from helpdesk.email import create_ticket_cc, HTML_EMAIL_ATTACHMENT_FILENAME, is_autoreply, send_info_email
from helpdesk.lib import process_attachments, safe_template_context
from helpdesk.models import FollowUp, Ticket
from helpdesk.signals import new_ticket_done, update_ticket_done


logger = logging.getLogger(__name__)


def custom_followup_display(followup_instance: FollowUp):
    """
    Custom display logic for FollowUp content.

    Checks for 'email_html_body.html' attachment and displays its content
    directly within a responsive iframe using srcdoc and Bootstrap 4 embed-responsive.
    Otherwise, displays the plain text comment with basic formatting.
    """
    if not followup_instance:
        return ""

    html_attachment = None
    html_content = None
    iframe_url = None  # Still useful for the fallback link

    # Check for the specific attachment
    try:
        html_attachment = followup_instance.followupattachment_set.filter(
            filename__iexact=HTML_EMAIL_ATTACHMENT_FILENAME
        ).first()

        if html_attachment and html_attachment.file:
            iframe_url = html_attachment.file.url  # Get URL for fallback link
            try:
                # Read the file content
                with html_attachment.file.open('rb') as f:
                    raw_content = f.read()
                # Decode assuming UTF-8, handle potential errors gracefully
                html_content = raw_content.decode('utf-8', errors='replace')
            except IOError as e:
                logger.error(
                    f"Error reading attachment file {html_attachment.file.name} for FollowUp {followup_instance.id}: {e}")
                html_content = None  # Ensure fallback if reading fails
            except UnicodeDecodeError as e:
                logger.error(
                    f"Error decoding attachment file {html_attachment.file.name} for FollowUp {followup_instance.id}: {e}")
                # Fallback: try decoding with a different common encoding or display an error message
                try:
                    html_content = raw_content.decode('iso-8859-1', errors='replace')
                except Exception:
                    html_content = "Error: Could not decode email content."

    except Exception as e:
        # Handle potential errors during query more broadly
        logger.error(f"Error accessing attachments for FollowUp {followup_instance.id}: {e}")
        html_attachment = None
        html_content = None

    if html_content is not None:
        # Attachment content read successfully, return the iframe HTML with srcdoc

        # Escape the HTML content *before* putting it in the srcdoc attribute
        escaped_html_content = escape(html_content.strip())
        print(escaped_html_content)

        # The fallback link still uses the original file URL
        fallback_link_url = escape(iframe_url) if iframe_url else "#"

        # --- MODIFICATION START ---
        # Choose an aspect ratio class. 'embed-responsive-4by3' or 'embed-responsive-16by9' are common.
        # You might experiment to see which looks best for typical emails.
        aspect_ratio_class = "embed-responsive-4by3"

        # Use Bootstrap's embed-responsive classes
        iframe_html = f"""
        <div class="embed-responsive {aspect_ratio_class} mb-2" style="border: 1px solid #ccc;">
             <iframe class="embed-responsive-item"
                     srcdoc="{escaped_html_content}"
                     sandbox="allow-same-origin allow-popups">
                 Your browser does not support iframes or the srcdoc attribute. Please
                 <a href="{fallback_link_url}" target="_blank" rel="noopener noreferrer">download the HTML body</a>.
             </iframe>
        </div>
        """
        # --- MODIFICATION END ---

        # Optional: Add back the original comment text link if desired
        # if followup_instance.comment:
        #    iframe_html += f"<hr><small>Original Comment Text:</small><div>{linebreaks(escape(followup_instance.comment))}</div>"
        safe_text = mark_safe(iframe_html)
        return safe_text
    else:
        # No specific attachment found, or failed to read/decode content, return plain text comment
        if followup_instance.comment:
            plain_text_html = linebreaks(escape(followup_instance.comment))
            return mark_safe(plain_text_html)
        else:
            return ""

def custom_create_object_from_email_message(message, ticket_id, payload, files, logger):
    ticket, previous_followup, new = None, None, False
    now = timezone.now()

    queue = payload["queue"]
    sender_email = payload["sender_email"]

    to_list = getaddresses(message.get_all("To", []))
    cc_list = getaddresses(message.get_all("Cc", []))

    message_id = message.get("Message-Id")
    in_reply_to = message.get("In-Reply-To")

    if message_id:
        message_id = message_id.strip()

    if in_reply_to:
        in_reply_to = in_reply_to.strip()

    if in_reply_to is not None:
        try:
            queryset = FollowUp.objects.filter(message_id=in_reply_to).order_by("-date")
            if queryset.count() > 0:
                previous_followup = queryset.first()
                ticket = previous_followup.ticket
        except FollowUp.DoesNotExist:
            pass  # play along. The header may be wrong

    if previous_followup is None and ticket_id is not None:
        try:
            ticket = Ticket.objects.get(id=ticket_id)
        except Ticket.DoesNotExist:
            ticket = None
        else:
            new = False
            # Check if the ticket has been merged to another ticket
            if ticket.merged_to:
                logger.info("Ticket has been merged to %s" % ticket.merged_to.ticket)
                # Use the ticket in which it was merged to for next operations
                ticket = ticket.merged_to
    # New issue, create a new <Ticket> instance
    if ticket is None:
        if not getattr(settings, "QUEUE_EMAIL_BOX_UPDATE_ONLY", False):
            ticket = Ticket.objects.create(
                title=payload["subject"],
                queue=queue,
                submitter_email=sender_email,
                created=now,
                description=payload["body"],
                priority=payload["priority"],
            )
            ticket.save()
            logger.debug("Created new ticket %s-%s" % (ticket.queue.slug, ticket.id))
            new = True
        else:
            # Possibly an email with no body but has an attachment
            logger.debug(
                "The QUEUE_EMAIL_BOX_UPDATE_ONLY setting is True so new ticket not created."
            )
            return None
    # Old issue being re-opened
    elif ticket.status in [Ticket.CLOSED_STATUS, Ticket.RESOLVED_STATUS]:
        ticket.status = Ticket.REOPENED_STATUS
        ticket.save()

    f = FollowUp(
        ticket=ticket,
        title=_(
            "E-Mail Received from %(sender_email)s" % {"sender_email": sender_email}
        ),
        date=now,
        public=True,
        comment=payload.get("full_body", payload["body"]) or "",
        message_id=message_id,
    )

    if ticket.status == Ticket.REOPENED_STATUS:
        f.new_status = Ticket.REOPENED_STATUS
        f.title = _(
            "Ticket Re-Opened by E-Mail Received from %(sender_email)s"
            % {"sender_email": sender_email}
        )

    f.save()
    logger.debug("Created new FollowUp for Ticket")

    logger.info(
        "[%s-%s] %s"
        % (
            ticket.queue.slug,
            ticket.id,
            ticket.title,
        )
    )

    if helpdesk_settings.HELPDESK_ENABLE_ATTACHMENTS:
        try:
            attached = process_attachments(f, files)
        except ValidationError as e:
            logger.error(str(e))
        else:
            for att_file in attached:
                logger.info(
                    "Attachment '%s' (with size %s) successfully added to ticket from email.",
                    att_file[0],
                    att_file[1].size,
                )

    context = safe_template_context(ticket)

    new_ticket_ccs = []
    new_ticket_ccs.append(create_ticket_cc(ticket, to_list + cc_list))

    autoreply = is_autoreply(message)
    if autoreply:
        logger.info(
            "Message seems to be auto-reply, not sending any emails back to the sender"
        )
    else:
        send_info_email(message_id, f, ticket, context, queue, new)
    if new:
        # emit signal when a new ticket is created
        new_ticket_done.send(sender="create_object_from_email_message", ticket=ticket)
    else:
        # emit signal with followup when the ticket is updated
        update_ticket_done.send(sender="create_object_from_email_message", followup=f)
    return ticket
