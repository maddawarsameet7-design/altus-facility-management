import os
from django.conf import settings
from django.core.files.storage import FileSystemStorage, Storage
from django.utils.functional import SimpleLazyObject


class PrivateFileSystemStorage(FileSystemStorage):
    """
    Local filesystem storage for private files (selfies, documents).
    Files are stored in settings.PRIVATE_STORAGE_ROOT and NEVER routed via public web servers.
    """
    def __init__(self, *args, **kwargs):
        location = getattr(settings, 'PRIVATE_STORAGE_ROOT', settings.BASE_DIR / 'private_media')
        super().__init__(location=str(location), *args, **kwargs)

    def url(self, name):
        # Disallow direct public URL construction
        return f"/api/roster/media/private/{name}"


def _resolve_private_storage():
    """
    Resolves private storage based on environment configuration.
    Uses S3/MinIO in production when AWS/S3 settings are provided;
    falls back to PrivateFileSystemStorage in local development / testing.
    """
    if os.environ.get('AWS_STORAGE_BUCKET_NAME') or getattr(settings, 'PRIVATE_STORAGE_BUCKET', None):
        try:
            from storages.backends.s3boto3 import S3Boto3Storage
            bucket_name = getattr(settings, 'PRIVATE_STORAGE_BUCKET', None) or os.environ.get('AWS_STORAGE_BUCKET_NAME')
            return S3Boto3Storage(
                bucket_name=bucket_name,
                default_acl='private',
                querystring_auth=True,
                querystring_expire=120  # 2-minute signed URL
            )
        except Exception:
            return PrivateFileSystemStorage()
    return PrivateFileSystemStorage()


private_storage_instance = SimpleLazyObject(_resolve_private_storage)


def get_private_storage():
    """Callable passed to models.FileField(storage=get_private_storage)."""
    return private_storage_instance

