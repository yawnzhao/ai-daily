#!/usr/bin/env python3
"""Synthesize an explicitly requested script or excerpt with the shared dictionary.

Credentials and audio stay outside Git. Existing output is never overwritten.
An uncertain request leaves a marker to prevent automatic duplicate billing.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import urllib.request


def load_dictionary(path):
    data = json.loads(path.read_text())['pronunciation_dict']
    rules = data['tone']
    if not isinstance(rules, list) or not all(isinstance(r, str) and '/' in r for r in rules):
        raise ValueError('Invalid pronunciation dictionary')
    return {'tone': rules}


def make_request(text, voice_id, dictionary):
    if not text.strip() or len(text) >= 10000:
        raise ValueError('Text must contain 1–9999 characters')
    return {'model': 'speech-2.8-hd', 'text': text, 'stream': False,
            'voice_setting': {'voice_id': voice_id, 'speed': 1.0, 'vol': 1.0, 'pitch': 0},
            'audio_setting': {'sample_rate': 44100, 'bitrate': 128000, 'format': 'mp3', 'channel': 1},
            'language_boost': 'Chinese', 'output_format': 'hex',
            'pronunciation_dict': dictionary}


def main():
    base = Path('/Users/imac-jd/我的云端硬盘/AI-Digest')
    parser = argparse.ArgumentParser()
    parser.add_argument('date', nargs='?')
    parser.add_argument('--text', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--dictionary', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if not args.date and not (args.text and args.output):
        parser.error('Supply date or both --text and --output')
    text_path = args.text or base / f'ai-daily-{args.date}-口播重写.txt'
    output = args.output or base / f'ai-daily-{args.date}-Cn1-speech-2.8-hd.mp3'
    dictionary_path = args.dictionary or Path(__file__).resolve().parents[1] / 'config/tts-pronunciation.json'
    text = text_path.read_text()
    dictionary = load_dictionary(dictionary_path)
    if args.dry_run:
        print(json.dumps({'characters': len(text), 'pronunciation_dict': dictionary,
                          'output': str(output)}, ensure_ascii=False))
        return
    if output.exists():
        raise SystemExit('Audio already exists; refusing to overwrite or synthesize again')
    output.parent.mkdir(parents=True, exist_ok=True)
    marker = output.with_suffix('.request-pending.json')
    if marker.exists():
        raise SystemExit('Earlier request has an uncertain outcome; inspect it before retrying')
    cfg = {}
    env_file = Path.home() / '.config/ai-digest/minimax.env'
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                k, v = line.split('=', 1)
                cfg[k.strip()] = v.strip().strip('\"\'')
    for key in ('MINIMAX_API_KEY', 'MINIMAX_VOICE_ID'):
        cfg[key] = os.environ.get(key) or cfg.get(key)
        if not cfg[key]:
            raise SystemExit('Missing required credential setting: ' + key)
    body = make_request(text, cfg['MINIMAX_VOICE_ID'], dictionary)
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    metadata = {'text_path': str(text_path), 'text_sha256': text_hash,
                'model': body['model'], 'voice_id': cfg['MINIMAX_VOICE_ID'], 'speed': 1.0,
                'pronunciation_dict': dictionary, 'output': str(output),
                'listening_review': 'pending_user_audition'}
    with marker.open('x') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    request = urllib.request.Request('https://api.minimax.cn/v1/t2a_v2',
        data=json.dumps(body).encode(), headers={'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + cfg['MINIMAX_API_KEY']})
    result = json.load(urllib.request.urlopen(request, timeout=300))
    status = result.get('base_resp', {}).get('status_code')
    if status != 0:
        raise SystemExit('MiniMax request did not succeed; status code: ' + str(status))
    payload = result.get('data', {}).get('audio', '')
    if not payload:
        raise SystemExit('No audio returned; do not automatically resubmit')
    audio = bytes.fromhex(payload)
    partial = output.with_suffix('.part')
    partial.write_bytes(audio)
    partial.rename(output)
    metadata.update(extra_info=result.get('extra_info'), trace_id=result.get('trace_id'),
                    audio_sha256=hashlib.sha256(audio).hexdigest(), audio_bytes=len(audio))
    receipt = (base / f'ai-daily-{args.date}-audio-receipt.json'
               if args.date and not args.output else output.with_suffix('.receipt.json'))
    receipt.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    marker.unlink()
    print(json.dumps({'saved': str(output), 'extra_info': result.get('extra_info')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
