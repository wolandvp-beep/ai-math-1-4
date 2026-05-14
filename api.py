from __future__ import annotations

import os
import re
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.platform.modules.core.public.services.access.config import build_public_product_config
from backend.platform.modules.core.public.services.access.service import (
    AccessService,
    AccessServiceError,
    LimitExceededError,
)
from backend.platform.modules.core.public.services.access.store import JsonAccessStateStore, resolve_state_file_path
from backend.service import APP_RELEASE, SOLVER_VERSION, attach_release, generate_explanation_response, prevalidate_explanation_request


app = FastAPI()
_ACCESS_SERVICE: AccessService | None = None
_ACCESS_SERVICE_STATE_PATH: str | None = None


CARD_DATA_BLOCK_MESSAGE = (
    'Данные банковской карты нельзя отправлять в приложение. '
    'Оплата подписки проходит только на стороне Robokassa.'
)


FRONTEND_EXPECTED_BACKEND_RELEASE = APP_RELEASE


def _version_payload() -> dict:
    return {
        'release': APP_RELEASE,
        'backendBuild': APP_RELEASE,
        'solverVersion': SOLVER_VERSION,
        'frontendExpectedBackend': FRONTEND_EXPECTED_BACKEND_RELEASE,
        'status': 'ok',
    }


def _json_error(status_code: int, content: dict) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=attach_release(content))


def _luhn_check(digits: str) -> bool:
    value = re.sub(r'\D+', '', str(digits or ''))
    if len(value) < 13 or len(value) > 19:
        return False
    if re.fullmatch(r'(\d)\1+', value):
        return False
    total = 0
    double_digit = False
    for char in reversed(value):
        n = int(char)
        if double_digit:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        double_digit = not double_digit
    return total % 10 == 0


def _contains_bank_card_details(text: str) -> bool:
    source = str(text or '')
    candidates = re.findall(r'(?:\d[\s-]?){13,19}', source)
    return any(_luhn_check(candidate) for candidate in candidates)


def get_access_service() -> AccessService:
    global _ACCESS_SERVICE, _ACCESS_SERVICE_STATE_PATH
    current_path = str(resolve_state_file_path())
    if _ACCESS_SERVICE is None or _ACCESS_SERVICE_STATE_PATH != current_path:
        _ACCESS_SERVICE = AccessService(JsonAccessStateStore(current_path))
        _ACCESS_SERVICE_STATE_PATH = current_path
    return _ACCESS_SERVICE

app.add_middleware(
    CORSMiddleware,
    allow_origins=['https://wolandvp-beep.github.io', 'http://localhost', 'http://127.0.0.1'],
    allow_credentials=False,
    allow_methods=['GET', 'POST', 'PATCH', 'OPTIONS'],
    allow_headers=['*'],
)


def _extract_bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get('Authorization', '').strip()
    if not auth_header.lower().startswith('bearer '):
        return None
    token = auth_header[7:].strip()
    return token or None


def _extract_install_id(request: Request, payload: dict | None = None) -> str | None:
    payload = payload or {}
    for key in ('X-Install-Id', 'X-Client-Id'):
        value = request.headers.get(key, '').strip()
        if value:
            return value
    for key in ('installId', 'clientId'):
        value = str(payload.get(key) or '').strip()
        if value:
            return value
    return None


def _error_payload(exc: AccessServiceError, *, access: dict | None = None) -> JSONResponse:
    content = {'error': str(exc), 'code': getattr(exc, 'code', 'access_error')}
    if access is not None:
        content['access'] = access
    return _json_error(getattr(exc, 'status_code', 400), content)


def _safe_access_status(*, token: str | None, install_id: str | None) -> dict | None:
    try:
        return get_access_service().get_access_status(token=token, install_id=install_id)
    except Exception:
        return None


async def _solve_text(*, text: str, token: str | None, install_id: str | None) -> JSONResponse | dict:
    if _contains_bank_card_details(text):
        access = _safe_access_status(token=token, install_id=install_id)
        content = attach_release({'error': CARD_DATA_BLOCK_MESSAGE, 'code': 'card_data_not_allowed'})
        if access is not None:
            content['access'] = access
        return _json_error(400, content)

    result: dict | None = None
    prevalidated = prevalidate_explanation_request(text)
    if prevalidated is not None:
        access = _safe_access_status(token=token, install_id=install_id)
        if 'error' in prevalidated:
            content = dict(prevalidated)
            if access is not None:
                content['access'] = access
            return _json_error(400, content)
        if access is not None:
            return attach_release({**prevalidated, 'access': access})
        return attach_release(prevalidated)
    try:
        access = get_access_service().record_final_submission(token=token, install_id=install_id)
    except LimitExceededError as exc:
        status = get_access_service().get_access_status(token=token, install_id=install_id)
        return _error_payload(exc, access=status)
    except AccessServiceError as exc:
        return _error_payload(exc)

    try:
        result = await generate_explanation_response(text)
        if 'error' in result:
            return _json_error(400, {**result, 'access': access})
        return attach_release({**result, 'access': access})
    except httpx.ReadTimeout:
        return _json_error(504, {'error': 'DeepSeek timeout: сервер не дождался ответа от API'})
    except httpx.ConnectTimeout:
        return _json_error(504, {'error': 'DeepSeek connect timeout: сервер не смог подключиться к API'})
    except httpx.ConnectError as exc:
        return _json_error(502, {'error': f'DeepSeek connect error: {str(exc)}'})
    except Exception as exc:  # pragma: no cover - runtime safety
        return _json_error(500, {'error': f'Server exception: {str(exc)}'})


@app.options('/')
@app.options('/api')
@app.options('/api/{path:path}')
async def options(path: str | None = None):
    return {'message': 'OK'}


@app.get('/')
@app.get('/api')
def read_root():
    product = build_public_product_config()
    return {
        **_version_payload(),
        'message': 'Математичка backend работает.',
        'provider': product['provider'],
        'platforms': product['distributionPlatforms'],
        'checkoutMode': product['checkoutMode'],
        'hint': 'POST / with action=explain or POST /api/explanations with {text}',
    }


@app.get('/version')
@app.get('/api/version')
def read_version():
    return _version_payload()


_DIAGNOSTIC_CASES = [
    ('multiline_guard', '2+2\n32-8', 'guard-multi-task', 'Ответ: Разделите задания'),
    ('joint_work_tractor', 'Один трактор может вспахать поле площадью 240 аров за 3 часа, а другой трактор — за 6 часов. За сколько часов вспашут поле оба трактора, работая вместе?', 'local:live-joint-work', 'за 2 часа'),
    ('joint_work_combine', 'Один комбайн убрал с поля 168 т пшеницы за 6 дней, а другой — столько же за 12 дней. За сколько дней уберут поле оба комбайна, работая вместе?', 'local:live-joint-work', 'за 4 дня'),
    ('system_comma', 'x + y = 10, y - x = 2', 'local:live-system-solver', 'x = 4, y = 6'),
    ('system_newline', 'x + y = 10\ny - x = 2', 'local:live-system-solver', 'x = 4, y = 6'),
    ('system_collapsed', 'x + y = 10 y - x = 2', 'local:live-system-solver', 'x = 4, y = 6'),
    ('motion_remaining', 'Велосипедист ехал 2 ч со скоростью 10 км/ч. После этого ему осталось проехать в 2 раза больше того, что он проехал. Сколько всего километров он должен проехать?', 'local:live-motion', '60 километров'),
    ('equal_groups_remaining', 'На 3 ветках по 9 шишек. Белка утащила 3 шишки. Сколько шишек осталось?', 'local:live-equal-groups', '24 шишки'),
    ('division_container', 'В коробки кладут по 6 яблок. Сколько коробок понадобится для 25 яблок?', 'local:live-division-containers', '5 коробок'),
    ('money_mixed', 'Сколько копеек в 3 рублях 50 копейках?', 'local:live-money-conversion', '350 копеек'),
]


@app.get('/api/diagnostics/live-smoke')
async def live_smoke_diagnostics():
    results = []
    bad_markers = ('Применяем правило:', 'Zad3', 'deterministic regression', 'lookup', 'answer map')
    for name, text, expected_source, expected_fragment in _DIAGNOSTIC_CASES:
        payload = await generate_explanation_response(text)
        result_text = str(payload.get('result') or '')
        source = str(payload.get('source') or '')
        issues = []
        if source != expected_source:
            issues.append(f'expected source {expected_source!r}, got {source!r}')
        if expected_fragment not in result_text:
            issues.append(f'missing result fragment {expected_fragment!r}')
        for marker in bad_markers:
            if marker.lower() in result_text.lower():
                issues.append(f'forbidden marker {marker!r}')
        results.append({
            'name': name,
            'ok': not issues,
            'issues': issues,
            'source': source,
            'expectedSource': expected_source,
            'resultPreview': result_text[:240],
        })
    passed = sum(1 for item in results if item['ok'])
    return {
        **_version_payload(),
        'diagnostic': 'live-smoke',
        'passed': passed,
        'total': len(results),
        'allPassed': passed == len(results),
        'results': results,
    }


@app.post('/')
async def proxy(request: Request):
    try:
        data = await request.json()
    except Exception:
        return _json_error(400, {'error': 'Некорректный JSON'})
    action = data.get('action')
    if action != 'explain':
        return _json_error(400, {'error': 'Invalid action'})
    text = data.get('text')
    return await _solve_text(text=text, token=_extract_bearer_token(request), install_id=_extract_install_id(request, data))


@app.post('/api/explanations')
@app.post('/api/explain')
async def explain_v2(request: Request):
    try:
        data = await request.json()
    except Exception:
        return _json_error(400, {'error': 'Некорректный JSON'})
    text = str(data.get('text') or '').strip()
    return await _solve_text(text=text, token=_extract_bearer_token(request), install_id=_extract_install_id(request, data))


@app.post('/explanations')
async def explain_without_api_prefix(request: Request):
    # Compatibility route for frontends configured with API_BASE_URL pointing to
    # the backend root instead of backend /api.  It returns the same JSON shape
    # as /api/explanations and prevents an HTML/static fallback from being
    # interpreted as an unclear server response.
    try:
        data = await request.json()
    except Exception:
        return _json_error(400, {'error': 'Некорректный JSON'})
    text = str(data.get('text') or '').strip()
    return await _solve_text(text=text, token=_extract_bearer_token(request), install_id=_extract_install_id(request, data))


@app.post('/api/auth/register')
async def auth_register(request: Request):
    payload = await request.json()
    try:
        return get_access_service().register(
            name=str(payload.get('name') or ''),
            email=str(payload.get('email') or ''),
            password=str(payload.get('password') or ''),
            install_id=_extract_install_id(request, payload),
        )
    except AccessServiceError as exc:
        return _error_payload(exc)


@app.post('/api/auth/login')
async def auth_login(request: Request):
    payload = await request.json()
    try:
        return get_access_service().login(
            email=str(payload.get('email') or ''),
            password=str(payload.get('password') or ''),
            install_id=_extract_install_id(request, payload),
        )
    except AccessServiceError as exc:
        return _error_payload(exc)


@app.post('/api/auth/recover')
async def auth_recover(request: Request):
    payload = await request.json()
    return get_access_service().recover(email=str(payload.get('email') or ''))


@app.post('/api/auth/logout')
async def auth_logout(request: Request):
    payload = await request.json() if request.method == 'POST' else {}
    token = _extract_bearer_token(request) or str(payload.get('token') or '') or None
    return get_access_service().logout(token=token)


@app.get('/api/user/profile')
async def get_profile(request: Request):
    try:
        return get_access_service().get_profile(token=_extract_bearer_token(request))
    except AccessServiceError as exc:
        return _error_payload(exc)


@app.patch('/api/user/profile')
async def patch_profile(request: Request):
    payload = await request.json()
    try:
        return get_access_service().update_profile(token=_extract_bearer_token(request), payload=payload)
    except AccessServiceError as exc:
        return _error_payload(exc)


@app.get('/api/billing/subscription')
async def get_subscription(request: Request):
    try:
        return get_access_service().get_subscription(
            token=_extract_bearer_token(request),
            install_id=_extract_install_id(request),
        )
    except AccessServiceError as exc:
        return _error_payload(exc)


@app.get('/api/billing/access-status')
async def get_access_status(request: Request):
    try:
        return get_access_service().get_access_status(
            token=_extract_bearer_token(request),
            install_id=_extract_install_id(request),
        )
    except AccessServiceError as exc:
        return _error_payload(exc)


@app.post('/api/billing/restore')
async def restore_billing(request: Request):
    try:
        return get_access_service().restore_purchase(token=_extract_bearer_token(request), install_id=_extract_install_id(request))
    except AccessServiceError as exc:
        return _error_payload(exc)


@app.post('/api/billing/web-session')
async def create_web_session(request: Request):
    payload = await request.json()
    try:
        return get_access_service().create_web_billing_session(token=_extract_bearer_token(request), install_id=_extract_install_id(request, payload), payload=payload)
    except AccessServiceError as exc:
        return _error_payload(exc)
