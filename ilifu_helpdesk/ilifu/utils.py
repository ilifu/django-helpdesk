
import logging
from django.utils.safestring import mark_safe
from django.utils.html import escape, linebreaks
from helpdesk.email import HTML_EMAIL_ATTACHMENT_FILENAME
from helpdesk.models import FollowUp

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
        print(safe_text)
        return safe_text
    else:
        # No specific attachment found, or failed to read/decode content, return plain text comment
        if followup_instance.comment:
            plain_text_html = linebreaks(escape(followup_instance.comment))
            return mark_safe(plain_text_html)
        else:
            return ""
