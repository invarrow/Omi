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
        'scope': 'openid email profile https://mail.google.com',
        'redirect_url': 'http://127.0.0.1:5000/chat-mail/auth',
        'access_type': 'offline',
    }
)

router.mount("/assets", StaticFiles(directory="templates", html=True), name="templates")

@router.get("/setup-chat-mail")
async def landing_page(request: Request, uid: str):
    request.session["user_uid"] = uid
    if not uid:
        raise HTTPException(status_code=400, detail='UID is required')
    return templates.TemplateResponse(
         name="setup_chat_mail.html" , context = {"request": request, "uid": uid})

@router.get('/chat-mail')
@router.post('/chat-mail')
async def chat_mail(request: Request, uid: str,data: dict):
    mail_api_key = get_chat_mail_api_key(uid)
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
    #client.token.push("client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET)

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
    print(data)
    query = data["prompt"]
    print(query)

    events = agent_executor.stream(
        {"messages": [("user", query)]},
        stream_mode="values",
    )
    response = ""
    for event in events:
        event["messages"][-1].pretty_print()
        response+=event["messages"][-1].content


    return {'message': response}


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
        return templates.TemplateResponse(
            name='error.html',
            context={'request': request, 'error': e.error}
        )

    user = token.get('userinfo')
    access_token = token.get('access_token')
    refresh_token = access_token
    #refresh_token = token.get('refresh_token')
    client_id = oauth.google.client_id
    client_secret = oauth.google.client_secret

    token["client_id"]=client_id
    token["client_secret"]=client_secret
    token["refresh_token"]=refresh_token

    import json
    f=open("token.json",'w')
    f.write(json.dumps(token))
    f.close()

    store_chat_mail_api_key(request.session['user_uid'], access_token)
    #store_mail_database_id(client.uid, mail_database_id)


    if user:
        request.session['user'] = dict(user)
    return RedirectResponse(f'/chat-mail/success')

@router.get('/chat-mail/success')
async def auth_successful(request: Request):
    #store_chat_mail_api_key(client.uid, client.access_token)
    print(request.session['user_uid'])
    return templates.TemplateResponse("success_page.html", {"request": request})



@router.get('/chat-mail/logout')
def logout(request: Request):
    request.session.pop('user')
    request.session.clear()
    return RedirectResponse('/')
