import os
from fastapi import APIRouter, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth, OAuthError
from db import *
import requests
from jose import jwt

import dotenv
dotenv.load_dotenv()

router = APIRouter()
#router.add_middleware(SessionMiddleware, secret_key="add any string...")

templates = Jinja2Templates(directory="templates")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Replace these with your own values from the Google Developer Console
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")

oauth = OAuth()
oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    client_kwargs={
        'scope': 'email openid profile',
        'redirect_url': 'http://127.0.0.1:5000/chat-mail/auth'
    }
)


router.mount("/assets", StaticFiles(directory="templates", html=True), name="templates")

@router.get("/setup-chat-mail")
async def landing_page(request: Request):
    return templates.TemplateResponse(
         name="index.html" , context = {"request": request}
)
@router.get("/chat-mail/login")
async def login(request: Request):
    url = request.url_for('auth')
    return await oauth.google.authorize_redirect(request, url)

@router.get('/setup/chat-mail', tags=['oauth'])
def is_setup_completed(uid: str):
    """
    Check if the user has setup the Notion CRM plugin.
    """
    notion_api_key = get_chat_mail_api_key(uid)
    notion_database_id = get_mail_database_id(uid)
    return {'is_setup_completed': notion_api_key is not None and notion_database_id is not None}

@router.get('/chat-mail/auth')
async def auth(request: Request,uid: str):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as e:
        print("HERE",e)
        return templates.TemplateResponse(
            name='error.html',
            context={'request': request, 'error': e.error}
        )
    user = token.get('userinfo')
    store_chat_mail_api_key(uid, token['access_token'])
    if user:
        request.session['user'] = dict(user)
    return RedirectResponse('/')


@router.get('/chat-mail/logout')
def logout(request: Request):
    request.session.pop('user')
    request.session.clear()
    return RedirectResponse('/')
