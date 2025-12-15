# app\core\use_cases\build_language.py
import structlog
from opentelemetry import trace
from app.core.ports.message_broker import IMessageBroker
from app.core.domain.events import SystemEvent, EventType, BuildRequestedPayload
from app.core.domain.exceptions import DomainError
from app.shared.observability import get_tracer

logger = structlog.get_logger()
tracer = get_tracer(__name__)

class BuildLanguage:
    """
    Use Case: Initiates the build process for a specific language.
    
    This is an Asynchronous Command. It does not wait for the build to finish.
    It publishes a 'language.build.requested' event and returns immediately.
    
    Responsibilities:
    1. Validate the build request parameters (strategy, lang_code).
    2. Construct the Domain Event.
    3. Publish to the Message Broker (Redis).
    """

    def __init__(self, broker: IMessageBroker):
        # Inject the IMessageBroker Port
        self.broker = broker

    async def execute(self, lang_code: str, strategy: str = "fast") -> str:
        """
        Triggers a language build. 

        Args:
            lang_code: ISO 639-3 code.
            strategy: 'fast' (Pidgin/Python) or 'full' (GF Compilation).

        Returns:
            str: The Event ID (Correlation ID) for tracking the request.
        """
        with tracer.start_as_current_span("use_case.build_language") as span:
            span.set_attribute("app.lang_code", lang_code)
            span.set_attribute("app.build_strategy", strategy)

            logger.info("build_request_received", lang=lang_code, strategy=strategy)

            try:
                # 1. Validate Strategy
                if strategy not in ["fast", "full"]:
                    raise DomainError(f"Invalid build strategy '{strategy}'. Use 'fast' or 'full'.")

                # 2. Create Payload (Pydantic models ensure correct serialization)
                payload = BuildRequestedPayload(
                    lang_code=lang_code,
                    strategy=strategy
                )

                # 3. Create System Event
                # We wrap the payload in the standard event envelope
                event = SystemEvent(
                    type=EventType.BUILD_REQUESTED,
                    payload=payload.model_dump()
                )

                # 4. Publish to Broker
                # The Worker service is listening for this specific event type
                await self.broker.publish(event)

                logger.info("build_event_published", event_id=event.id, lang=lang_code)
                
                # Return the ID so the client can poll for status updates
                return event.id

            except Exception as e:
                logger.error("build_request_failed", error=str(e), exc_info=True)
                raise DomainError(f"Failed to queue build request: {str(e)}")