"""Routines to manage the baroque Floydhub login process."""

import os

from floyd.client.auth import AuthClient
from floyd.client.experiment import ExperimentClient
from floyd.manager.auth_config import AuthConfigManager
from floyd.model.access_token import AccessToken
from floyd.model.credentials import Credentials

def get_client():
    """Instantiate the Floyd ExperimentClient"""
    return ExperimentClient()
    
def login(username=os.environ['FLOYDHUB_USERNAME'],
          password=os.environ['FLOYDHUB_PASSWORD']):
    """Login to Floydhub and set the access token. 

    Returns: The Floyd user instance
    """
    credentials = Credentials(username=username, password=password)

    auth = AuthClient()
    access_code = auth.login(credentials)
    user = auth.get_user(access_code)
    access_token = AccessToken(username=user.username, token=access_code)
    
    AuthConfigManager.set_access_token(access_token)
    return user
