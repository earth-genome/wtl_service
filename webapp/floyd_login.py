"""Routines to manage the baroque Floydhub login process."""

import os

from floyd.client.auth import AuthClient
from floyd.client.experiment import ExperimentClient
from floyd.exceptions import FloydException
from floyd.manager.auth_config import AuthConfigManager
from floyd.model.access_token import AccessToken
from floyd.model.credentials import Credentials

AUTH_ENV_VARS = {
    'username': 'FLOYDHUB_USERNAME',
    'password': 'FLOYDHUB_PASSWORD'
}

def get_client():
    """Instantiate the Floyd ExperimentClient"""
    return ExperimentClient()
    
def login(username=None, password=None):
    """Login to Floydhub and set the access token. 

    Returns: The Floyd user instance
    """
    if not username:
        username = os.environ[AUTH_ENV_VARS['username']]
    if not password:
        password = os.environ[AUTH_ENV_VARS['password']]
    credentials = Credentials(username=username, password=password)

    auth = AuthClient()
    access_code = auth.login(credentials)
    user = auth.get_user(access_code)
    access_token = AccessToken(username=user.username, token=access_code)
    
    AuthConfigManager.set_access_token(access_token)
    return user
