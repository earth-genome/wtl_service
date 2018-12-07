"""Routines to manage the ungainly Floydhub login process."""

import os

import floyd.client.auth
import floyd.client.experiment
import floyd.manager.auth_config
import floyd.model.access_token
import floyd.model.credentials

def get_client():
    """Instantiate the Floyd ExperimentClient"""
    return floyd.client.experiment.ExperimentClient()
    
def login(username=os.environ['FLOYDHUB_USERNAME'],
          password=os.environ['FLOYDHUB_PASSWORD']):
    """Login to Floydhub and set the access token."""
    credentials = floyd.model.credentials.Credentials(
        username=username, password=password)

    auth = floyd.client.auth.AuthClient()
    access_code = auth.login(credentials)
    user = auth.get_user(access_code)
    access_token = floyd.model.access_token.AccessToken(
        username=user.username, token=access_code)
    
    floyd.manager.auth_config.AuthConfigManager.set_access_token(access_token)
    return user
