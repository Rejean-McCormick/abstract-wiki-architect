# app\adapters\s3_repo.py
# app/adapters/s3_repo.py
import asyncio
import boto3
from botocore.exceptions import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.ports import LanguageRepo
from app.shared.config import settings
from app.shared.telemetry import get_tracer

tracer = get_tracer(__name__)

class S3LanguageRepo(LanguageRepo):
    """
    Production Persistence Adapter.
    Stores compiled PGF grammar binaries in an AWS S3 Bucket.
    """

    def __init__(self):
        # Initialize Boto3 Client
        # We don't need to pass credentials explicitly if they are in env vars 
        # (AWS_ACCESS_KEY_ID, etc.), which boto3 detects automatically.
        self.s3_client = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        self.bucket = settings.AWS_BUCKET_NAME

    async def save_pgf(self, language_code: str, binary_content: bytes) -> None:
        """
        Uploads the compiled PGF binary to S3.
        Non-blocking (runs in thread pool).
        """
        key = self._get_s3_key(language_code)
        
        with tracer.start_as_current_span("s3_upload") as span:
            span.set_attribute("s3.bucket", self.bucket)
            span.set_attribute("s3.key", key)
            
            await asyncio.to_thread(
                self._upload_sync, key, binary_content
            )

    async def get_pgf(self, language_code: str) -> bytes:
        """
        Downloads the PGF binary from S3.
        Returns bytes or raises FileNotFoundError if missing.
        """
        key = self._get_s3_key(language_code)
        
        with tracer.start_as_current_span("s3_download") as span:
            span.set_attribute("s3.bucket", self.bucket)
            span.set_attribute("s3.key", key)
            
            try:
                return await asyncio.to_thread(self._download_sync, key)
            except ClientError as e:
                # Map S3 404 to Domain-level NotFound
                if e.response['Error']['Code'] == "404" or e.response['Error']['Code'] == 'NoSuchKey':
                    raise FileNotFoundError(f"Grammar for {language_code} not found in S3.")
                raise e

    # --- Synchronous Helpers (executed in thread pool) ---

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(ClientError)
    )
    def _upload_sync(self, key: str, data: bytes):
        """Sync boto3 upload with retries."""
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType="application/octet-stream"
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(ClientError)
    )
    def _download_sync(self, key: str) -> bytes:
        """Sync boto3 download with retries."""
        response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def _get_s3_key(self, language_code: str) -> str:
        """Standardizes naming convention: e.g., 'grammars/Finnish.pgf'"""
        # Assuming language_code is ISO or similar (e.g., 'fin', 'ara')
        # You might want to map 'fin' -> 'Finnish' if your core uses full names,
        # but using the code is safer for persistence keys.
        return f"grammars/{language_code}.pgf"