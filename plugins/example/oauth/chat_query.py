import os

from fastapi import APIRouter, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
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

class Client:
  uid:str
  access_token:str
  token:str


client = Client()
router.mount("/assets", StaticFiles(directory="templates", html=True), name="templates")

@router.get("/setup-chat-mail")
async def landing_page(request: Request, uid: str):
    client.uid = uid
    return templates.TemplateResponse(
         name="setup_chat_mail.html" , context = {"request": request, "uid": uid})

@router.get('/chat-mail')
async def chat_mail(request: Request):
    mail_api_key = client.access_token
    if not mail_api_key: return {'message': 'Chat with Mail plugin is not setup properly, check your plugin settings.'}

    from langchain_google_community import GmailToolkit
    from langchain_google_community.gmail.utils import (
        build_resource_service,
        get_gmail_credentials,
    )

    from langchain_groq import ChatGroq
    from langgraph.prebuilt import create_react_agent
    # Can review scopes here https://developers.google.com/gmail/api/auth/scopes
    # For instance, readonly scope is 'https://www.googleapis.com/auth/gmail.readonly'
    import json
    with open("token.json", "w") as file:
      json.dump(client.token, file)

    credentials = get_gmail_credentials(
        token_file="token.json",
        scopes=["https://mail.google.com/"],
        client_secrets_file="credentials.json",
    )
    api_resource = build_resource_service(credentials=credentials)
    toolkit = GmailToolkit(api_resource=api_resource)



    llm = ChatGroq(model="llama3-8b-8192")
    tools = toolkit.get_tools()


    agent_executor = create_react_agent(llm, tools)
    example_query = "Draft an email to fake@fake.com thanking them for coffee."

    events = agent_executor.stream(
        {"messages": [("user", example_query)]},
        stream_mode="values",
    )
    print("TEA")
    for event in events:
        event["messages"][-1].pretty_print()


@router.get("/chat-mail/login")
async def login(request: Request):
    url = request.url_for('auth')
    return await oauth.google.authorize_redirect(request, url)

@router.get('/setup/chat-mail', tags=['oauth'])
def is_setup_completed(uid: str):
    """
    Check if the user has setup the Notion CRM plugin.
    """
    mail_api_key = get_chat_mail_api_key(uid)
    mail_database_id = get_mail_database_id(uid)
    return {'is_setup_completed': mail_api_key is not None and mail_database_id is not None}

@router.get('/chat-mail/auth')
async def auth(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as e:
        print("HERE",e)
        return templates.TemplateResponse(
            name='error.html',
            context={'request': request, 'error': e.error}
        )
    user = token.get('userinfo')
    print(type(token))
    client.access_token = token.get('access_token')
    client.token = token
    if user:
        request.session['user'] = dict(user)
    return RedirectResponse(f'/chat-mail/success')

@router.get('/chat-mail/success')
async def auth_successful(request: Request):
    #store_chat_mail_api_key(client.uid, client.access_token)
    return RedirectResponse(
        f'/chat-mail'
    )



@router.get('/chat-mail/logout')
def logout(request: Request):
    request.session.pop('user')
    request.session.clear()
    return RedirectResponse('/')
