import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class IlifuConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ilifu'

    def ready(self):
        try:
            from helpdesk.models import FollowUp
            from .utils import custom_followup_display

            FollowUp.get_markdown = custom_followup_display
            logger.info("Successfully monkey-patched helpdesk.models.FollowUp.get_markdown")

        except ImportError as e:
            logger.error(f"Failed to monkey-patch helpdesk models: {e}")
            # Decide if this is critical; pass might hide issues during startup
            pass
