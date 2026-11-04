"""Small, synchronous JSON hook bridge. Qt is never imported in a hook process."""
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone

from codex_bridge import actor_path, atomic_json, publish_event
from family_store import EVENT_STATUS
from linux.paths import approval_mode, pid_alive, read_json, state_dir, utc_now

EVENTS = ('SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PostToolUse',
          'PreCompact', 'PostCompact', 'SubagentStart', 'SubagentStop',
          'Stop', 'Interrupt', 'SessionEnd', 'PermissionRequest')


def redact(value):
    value = str(value)
    value = re.sub(r'(?i)([\"\']?(?:api[_-]?key|token|secret|password)[\"\']?\s*[:=]\s*)[\"\']?[^\"\'\s,;]+', r'\1[redacted]', value)
    value = re.sub(r'(?i)(authorization:\s*bearer\s+)\S+', r'\1[redacted]', value)
    return re.sub(r'[A-Za-z0-9_-]{72,}', '[redacted-token]', value)


def permission_summary(payload):
    tool = str(payload.get('tool_name') or 'Codex')
    detail = payload.get('tool_input')
    if not detail:
        return ''
    if not isinstance(detail, dict):
        return redact(f'{tool}\n{detail}')
    command = detail.get('command') or detail.get('cmd') or detail.get('patch') or detail.get('input')
    description = detail.get('description') or detail.get('justification')
    if command:
        text = f'{tool}\n{description or ""}\n{command}'
    else:
        text = tool+'\n'+json.dumps(detail, ensure_ascii=False, indent=2)
    return redact(text)


def heartbeat_fresh(directory, now=None):
    heartbeat = read_json(directory/'pig-heartbeat.json') or {}
    try:
        stamp = datetime.fromisoformat(heartbeat['updated_at'].replace('Z', '+00:00')).timestamp()
        return -2 <= (time.time() if now is None else now)-stamp < 5 and pid_alive(heartbeat.get('pid'))
    except (KeyError, TypeError, ValueError):
        return False


def event_payload(payload, event=None, status=None):
    event = event or payload.get('hook_event_name', '')
    result = {key: payload[key] for key in ('session_id', 'turn_id', 'agent_id', 'parent_thread_id',
              'transcript_path', 'cwd', 'thread_title', 'internal_request_kind') if key in payload}
    if event == 'UserPromptSubmit':
        result['prompt_preview'] = redact(payload.get('prompt', ''))[:400]
    result.update(event=event, status=status or EVENT_STATUS.get(event, 'idle'),
                  source='googlepiggy-linux', updated_at=utc_now())
    return result


def request_permission(payload, directory, timeout=590):
    summary = permission_summary(payload)
    if not summary or not heartbeat_fresh(directory):
        return {}
    request_id = uuid.uuid4().hex
    requests = directory/'permission-requests'
    request = requests/(request_id+'.request.json')
    response = requests/(request_id+'.response.json')
    now = time.time()
    mode = approval_mode(directory)
    expires = now+(60 if mode == 'codex' else timeout)
    atomic_json(request, dict(request_id=request_id, created_at=utc_now(),
                expires_at=datetime.fromtimestamp(expires, timezone.utc).isoformat(),
                session_id=payload.get('session_id', ''), agent_id=payload.get('agent_id', ''),
                turn_id=payload.get('turn_id', ''), tool_name=payload.get('tool_name', 'Codex'),
                summary=summary, hook_pid=os.getpid(), approval_mode=mode))
    publish_event(directory, dict(event_payload(payload), permission_request_id=request_id))
    if mode == 'codex':
        return {}  # Native approval proceeds immediately; the file is only a UI notice.
    actor = payload.get('agent_id') or payload.get('session_id')
    try:
        while time.time()-now < timeout:
            state = read_json(actor_path(directory, actor)) if actor else {}
            if not isinstance(state, dict):
                return {}
            if (state.get('event') in {'Interrupt', 'SessionEnd', 'Stop', 'SubagentStop'} or
                state.get('turn_id') and payload.get('turn_id') and state['turn_id'] != payload['turn_id']):
                # The newer turn/terminal event is authoritative. Never replace
                # it with an old permission's idle status or permission decision.
                return {}
            if not heartbeat_fresh(directory):
                break
            reply = read_json(response)
            if reply is not None:
                if not isinstance(reply, dict) or reply.get('request_id') != request_id or reply.get('decision') not in {'allow', 'deny'}:
                    break
                decision = {'behavior': reply['decision']}
                if decision['behavior'] == 'deny':
                    decision['message'] = '用户从 GooglePiggy 拒绝本次请求。'
                publish_event(directory, event_payload(payload, 'PermissionDecision', 'working' if decision['behavior'] == 'allow' else 'idle'))
                return {'hookSpecificOutput': {'hookEventName': 'PermissionRequest', 'decision': decision}}
            time.sleep(.15)
        publish_event(directory, event_payload(payload, 'PermissionNoDecision', 'idle'))
        return {}
    finally:
        request.unlink(missing_ok=True)
        response.unlink(missing_ok=True)


def handle(payload, directory=None, permission_timeout=590):
    if not isinstance(payload, dict) or payload.get('hook_event_name') not in EVENTS:
        return {}
    directory = directory or state_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if payload['hook_event_name'] == 'PermissionRequest':
        return request_permission(payload, directory, permission_timeout)
    if payload.get('session_id'):
        publish_event(directory, event_payload(payload))
    return {}


def main():
    # The decorative bridge must leave normal Codex operation available on failure.
    try:
        raw = sys.stdin.buffer.read(2_000_001)
        result = handle(json.loads(raw)) if len(raw) <= 2_000_000 else {}
    except (OSError, ValueError, TypeError, KeyError):
        result = {}
    print(json.dumps(result, ensure_ascii=False))
