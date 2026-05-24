import base64
import os
import shutil
import tempfile
import zipfile
from typing import Dict, Any, List, Union

RUNTIME_TEMPLATES = [
    {
        'runtime': 'nodejs18.x',
        'fileName': 'index.js',
        'handler': 'index.handler',
        'source': """exports.handler = async (event) => {
  return {
    statusCode: 200,
    body: JSON.stringify({
      message: "Hello from Floci Lambda",
      event
    })
  };
};
"""
    },
    {
        'runtime': 'python3.9',
        'fileName': 'index.py',
        'handler': 'index.handler',
        'source': """import json


def handler(event, context):
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Hello from Floci Lambda",
            "event": event,
        }),
    }
"""
    }
]

def get_runtime_templates():
    return RUNTIME_TEMPLATES

def get_runtime_template(runtime: str):
    for template in RUNTIME_TEMPLATES:
        if template['runtime'] == runtime:
            return template
    return None

class PreparedLambdaPackage:
    def __init__(self, zip_path: str, working_dir: str):
        self.zip_path = zip_path
        self.working_dir = working_dir

    def cleanup(self):
        shutil.rmtree(self.working_dir, ignore_errors=True)

def strip_base64_prefix(value: str) -> str:
    import re
    return re.sub(r'^data:.*?;base64,', '', value)

def sanitize_zip_entry_name(file_name: str) -> str:
    normalized = file_name.replace('\\', '/').lstrip('/')
    parts = [p for p in normalized.split('/') if p]

    if not parts or any(p in ['.', '..'] for p in parts):
        raise ValueError(f"Invalid ZIP entry path: {file_name}")

    return '/'.join(parts)

def _write_zip_entries(zipf: zipfile.ZipFile, entries: List[Dict[str, bytes]]):
    for entry in entries:
        zipf.writestr(entry['name'], entry['content'])

def prepare_lambda_package(runtime: str, code: Dict[str, Any]) -> PreparedLambdaPackage:
    working_directory = tempfile.mkdtemp(prefix='floci-lambda-')
    zip_path = os.path.join(working_directory, 'function.zip')

    try:
        mode = code.get('mode')
        if mode == 'zipBase64':
            zip_content = base64.b64decode(strip_base64_prefix(code['zipBase64']))
            with open(zip_path, 'wb') as f:
                f.write(zip_content)
            return PreparedLambdaPackage(zip_path, working_directory)

        entries = resolve_zip_entries(runtime, code)
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            _write_zip_entries(zipf, entries)

        return PreparedLambdaPackage(zip_path, working_directory)
    except Exception as e:
        shutil.rmtree(working_directory, ignore_errors=True)
        raise e

def resolve_zip_entries(runtime: str, code: Dict[str, Any]) -> List[Dict[str, bytes]]:
    mode = code.get('mode')
    if mode == 'template':
        template = get_runtime_template(runtime)
        if not template:
            raise ValueError(f"Runtime {runtime} requires an uploaded deployment ZIP.")
        return [{'name': template['fileName'], 'content': template['source'].encode('utf-8')}]

    if mode == 'inline':
        return [{
            'name': sanitize_zip_entry_name(code['fileName']),
            'content': code['source'].encode('utf-8')
        }]

    if mode == 'files':
        return [{
            'name': sanitize_zip_entry_name(file['fileName']),
            'content': file['source'].encode('utf-8')
        } for file in code.get('files', [])]

    return []
