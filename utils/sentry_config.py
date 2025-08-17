import sentry_sdk
import os
from dotenv import load_dotenv
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.threading import ThreadingIntegration
from utils.logging_config import get_logger

logger = get_logger(__name__)

def initialize_sentry():
    """
    Initialize Sentry for error monitoring and performance tracking.
    
    Environment variables:
    - SENTRY_DSN: Your Sentry project DSN
    - SENTRY_ENVIRONMENT: Environment name (e.g., 'production', 'development')
    - SENTRY_TRACES_SAMPLE_RATE: Sample rate for performance monitoring (0.0 to 1.0)
    """
    # Load environment variables from .env file
    load_dotenv()
    
    dsn = os.getenv('SENTRY_DSN')
    
    if not dsn:
        logger.info("Sentry DSN not configured. Skipping Sentry initialization.")
        return False
    
    environment = os.getenv('SENTRY_ENVIRONMENT', 'development')
    traces_sample_rate = float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1'))
    
    # Configure logging integration
    logging_integration = LoggingIntegration(
        level=None,  # Capture records from all log levels
        event_level=None  # Don't send log records as events by default
    )
    
    # Configure threading integration for GUI applications
    threading_integration = ThreadingIntegration(propagate_hub=True)
    
    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=traces_sample_rate,
            integrations=[
                logging_integration,
                threading_integration,
            ],
            # Additional configuration
            attach_stacktrace=True,
            send_default_pii=False,  # Don't send personally identifiable information
            max_breadcrumbs=50,
            before_send=before_send_filter,
        )
        
        logger.info(f"Sentry initialized successfully. Environment: {environment}, Sample rate: {traces_sample_rate}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")
        return False

def before_send_filter(event, hint):
    """
    Filter events before sending to Sentry.
    This allows you to modify or drop events based on your needs.
    """
    # Skip events from certain modules if needed
    if 'exc_info' in hint:
        exc_type, exc_value, tb = hint['exc_info']
        # You can add custom filtering logic here
        
    return event

def capture_exception_with_context(exception, **context):
    """
    Capture an exception with additional context.
    
    Args:
        exception: The exception to capture
        **context: Additional context to include with the error
    """
    with sentry_sdk.configure_scope() as scope:
        for key, value in context.items():
            scope.set_tag(key, value)
        
        sentry_sdk.capture_exception(exception)

def capture_message_with_context(message, level='info', **context):
    """
    Capture a message with additional context.
    
    Args:
        message: The message to capture
        level: Log level ('debug', 'info', 'warning', 'error', 'fatal')
        **context: Additional context to include
    """
    with sentry_sdk.configure_scope() as scope:
        for key, value in context.items():
            scope.set_tag(key, value)
        
        sentry_sdk.capture_message(message, level)

def set_user_context(user_id=None, username=None, email=None, **extra):
    """
    Set user context for Sentry events.
    
    Args:
        user_id: User identifier
        username: Username
        email: User email
        **extra: Additional user properties
    """
    with sentry_sdk.configure_scope() as scope:
        scope.set_user({
            "id": user_id,
            "username": username,
            "email": email,
            **extra
        })

def add_breadcrumb(message, category=None, level='info', data=None):
    """
    Add a breadcrumb to track user actions or events.
    
    Args:
        message: Breadcrumb message
        category: Category of the breadcrumb
        level: Log level
        data: Additional data
    """
    sentry_sdk.add_breadcrumb({
        'message': message,
        'category': category or 'default',
        'level': level,
        'data': data or {}
    })

def start_transaction(name, op=None):
    """
    Start a performance transaction.
    
    Args:
        name: Transaction name
        op: Operation type
        
    Returns:
        Transaction object
    """
    return sentry_sdk.start_transaction(name=name, op=op)