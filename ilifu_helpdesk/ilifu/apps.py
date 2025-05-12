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

            import helpdesk.email as helpdesk_email_module
            from .utils import custom_create_object_from_email_message

            helpdesk_email_module.create_object_from_email_message = custom_create_object_from_email_message
            logger.info("Successfully monkey-patched helpdesk.email.create_object_from_email_message")

        except ImportError as e:
            logger.error(f"Failed to import modules for monkey-patching: {e}")
            # Decide if this is critical; pass might hide issues during startup
            pass

        except Exception as e:
            logger.error(f'An unexpected error has occurred during monkey patching: {e}')
            pass
