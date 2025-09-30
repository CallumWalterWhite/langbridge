from authlib.integrations.starlette_client import OAuth
import yaml

from schemas.auth import AuthManifest
from config import settings
    
def __get_oauth_manifest() -> AuthManifest:
    with open("auth/auth_manifest.yml", "r") as f:
        manifest_dict = yaml.safe_load(f)
    return AuthManifest.model_validate(manifest_dict)

def create_oauth_client() -> OAuth:
    oauth = OAuth()
    manifest = __get_oauth_manifest()
    
    for registry in manifest.registries:
        oauth.register(
            name=registry.type,
            client_id=settings.__getattribute__(registry.client_id.upper()),
            client_secret=settings.__getattribute__(registry.client_secret.upper()),
            authorize_url=settings.__getattribute__(registry.authorize_url.upper()),
            access_token_url=settings.__getattribute__(registry.access_token_url.upper()),
            api_base_url=settings.__getattribute__(registry.api_base_url.upper()),
            client_kwargs={"scope": " ".join(registry.scopes)},
            
        )
    return oauth