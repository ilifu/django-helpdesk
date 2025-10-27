"""
Monkey patch for django-helpdesk to fix Unicode encoding issues in email processing.

The issue occurs when emails contain non-ASCII characters (like ©) in multipart MIME parts.
The default email policy uses ASCII encoding which causes UnicodeEncodeError.
"""

import logging
from email import policy as email_policy
from email.generator import BytesGenerator
import io

logger = logging.getLogger(__name__)


def patched_as_bytes(self, unixfrom=False, *args, **kwargs):
    """
    Patched version of MIMEPart.as_bytes() that handles non-ASCII content correctly.

    Uses the compat32 policy which handles UTF-8 encoding more gracefully than
    the default policy when encountering non-ASCII characters.
    """
    try:
        # Try the default method first
        fp = io.BytesIO()
        g = BytesGenerator(fp, mangle_from_=False, policy=email_policy.compat32)
        g.flatten(self, unixfrom=unixfrom)
        return fp.getvalue()
    except UnicodeEncodeError as e:
        logger.warning(
            f"UnicodeEncodeError when serializing MIME part: {e}. "
            "Attempting fallback with surrogateescape error handling."
        )
        # Fallback: try with utf-8 encoding
        try:
            fp = io.BytesIO()
            # Use a custom policy that allows UTF-8 encoding
            utf8_policy = email_policy.compat32.clone(utf8=True)
            g = BytesGenerator(fp, mangle_from_=False, policy=utf8_policy)
            g.flatten(self, unixfrom=unixfrom)
            return fp.getvalue()
        except Exception as fallback_error:
            logger.error(
                f"Failed to serialize MIME part even with UTF-8 fallback: {fallback_error}. "
                "Using payload as bytes directly."
            )
            # Last resort: return the payload as-is
            payload = self.get_payload(decode=True)
            if isinstance(payload, bytes):
                return payload
            return str(payload).encode('utf-8', errors='replace')


def apply_patches():
    """Apply all monkey patches to django-helpdesk."""
    try:
        from email.message import MIMEPart

        # Replace the as_bytes method
        MIMEPart.as_bytes = patched_as_bytes

        logger.info("Successfully applied django-helpdesk email encoding patch")
    except Exception as e:
        logger.error(f"Failed to apply email encoding patch: {e}")


# Auto-apply patches when this module is imported
apply_patches()
