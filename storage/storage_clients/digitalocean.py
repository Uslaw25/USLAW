from typing import Any, Dict, Union
from chainlit.logger import logger
from chainlit import make_async
import boto3
from abc import ABC, abstractmethod

EXPIRY_TIME = 3600  # 1 hour


class BaseStorageClient(ABC):
    @abstractmethod
    async def get_read_url(self, object_key: str) -> str:
        pass

    @abstractmethod
    async def upload_file(
        self,
        object_key: str,
        data: Union[bytes, str],
        mime: str = "application/octet-stream",
        overwrite: bool = True,
    ) -> Dict[str, Any]:
        pass


class DigitalOceanStorageClient(BaseStorageClient):
    """
    Storage client for DigitalOcean Spaces (S3-compatible)
    """

    def __init__(
        self,
        bucket: str,
        region_name: str,
        access_key_id: str,
        secret_access_key: str,
        endpoint_url: str = None,
    ):
        try:
            self.bucket = bucket
            self.region_name = region_name
            self.endpoint_url = endpoint_url or f"https://{region_name}.digitaloceanspaces.com"
            self.client = boto3.client(
                "s3",
                region_name=region_name,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                endpoint_url=self.endpoint_url,
            )
            logger.info("DigitalOceanStorageClient initialized")
        except Exception as e:
            logger.warning(f"DigitalOceanStorageClient initialization error: {e}")

    def sync_get_read_url(self, object_key: str) -> str:
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": object_key},
                ExpiresIn=EXPIRY_TIME,
            )
            logger.info(f"Generated presigned URL for {object_key}")
            return url
        except Exception as e:
            logger.warning(f"DigitalOceanStorageClient get_read_url error: {e}")
            return object_key

    async def get_read_url(self, object_key: str) -> str:
        return await make_async(self.sync_get_read_url)(object_key)

    def sync_upload_file(
        self,
        object_key: str,
        data: Union[bytes, str],
        mime: str = "application/octet-stream",
        overwrite: bool = True,
    ) -> Dict[str, Any]:
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=object_key,
                Body=data,
                ContentType=mime,
                ACL="public-read",  # optional, if you want public access
            )
            url = f"https://{self.bucket}.{self.region_name}.digitaloceanspaces.com/{object_key}"
            logger.info(f"Uploaded file to {url}")
            return {"object_key": object_key, "url": url, "status": "uploaded"}
        except Exception as e:
            logger.warning(f"DigitalOceanStorageClient upload_file error: {e}")
            return {"object_key": object_key, "status": "error", "error": str(e)}

    async def upload_file(
        self,
        object_key: str,
        data: Union[bytes, str],
        mime: str = "application/octet-stream",
        overwrite: bool = True,
    ) -> Dict[str, Any]:
        return await make_async(self.sync_upload_file)(object_key, data, mime, overwrite)

    async def close(self) -> None:
        return
