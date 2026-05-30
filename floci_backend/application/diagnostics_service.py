import base64
import json
import os
import shutil
import tempfile
import time
from typing import Dict, Any, List, Optional
from floci_backend.infrastructure.aws_cli import AwsCli, AwsCliError
from floci_backend.application.compatibility_service import CompatibilityService

class DiagnosticsService:
    def __init__(self, aws_cli: AwsCli, compatibility_service: Optional[CompatibilityService] = None):
        self.aws_cli = aws_cli
        self.compatibility_service = compatibility_service

    async def run_cost_forecast(self) -> Dict[str, Any]:
        forecasts = []
        total_monthly_forecast = 0.0

        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            pricing_book_path = os.path.join(current_dir, '..', 'infrastructure', 'pricing-book.json')

            try:
                with open(pricing_book_path, 'r', encoding='utf-8') as f:
                    pricing_book = json.load(f)
                    rates = pricing_book.get('rates', {})
            except FileNotFoundError:
                rates = {}

            # 1. S3 Buckets
            s3_count = 0
            s3_source = 'fallback-zero'
            try:
                payload = await self.aws_cli.run_json(['s3api', 'list-buckets'])
                s3_count = len(payload.get('Buckets', []))
                s3_source = 'real-aws-cli'
            except Exception:
                if self.compatibility_service:
                    compat = await self.compatibility_service.get_resource('s3', 'buckets')
                    s3_count = compat.get('count', 0) if compat else 0
                    s3_source = 'sidecar-compat'

            s3_rate = rates.get('s3.storage', {}).get('price', 0.023)
            s3_monthly = round(s3_count * 50 * s3_rate, 2)
            forecasts.append({
                'service': 'S3 Buckets',
                'resourceType': 'Buckets',
                'count': s3_count,
                'unitPrice': round(50 * s3_rate, 4),
                'monthly': s3_monthly,
                'source': s3_source,
            })

            # 2. EC2 Instances
            ec2_count = 0
            ec2_source = 'fallback-zero'
            try:
                payload = await self.aws_cli.run_json(['ec2', 'describe-instances'])
                ec2_count = sum(len(res.get('Instances', [])) for res in payload.get('Reservations', []))
                ec2_source = 'real-aws-cli'
            except Exception:
                if self.compatibility_service:
                    compat = await self.compatibility_service.get_resource('ec2', 'instances')
                    ec2_count = compat.get('count', 0) if compat else 0
                    ec2_source = 'sidecar-compat'

            ec2_rate = rates.get('ec2.instance', {}).get('price', 0.0104)
            ec2_monthly = round(ec2_count * 730 * ec2_rate, 2)
            forecasts.append({
                'service': 'EC2',
                'resourceType': 'Instances',
                'count': ec2_count,
                'unitPrice': round(730 * ec2_rate, 4),
                'monthly': ec2_monthly,
                'source': ec2_source,
            })

            # 3. Lambda Functions
            lambda_count = 0
            lambda_source = 'fallback-zero'
            try:
                payload = await self.aws_cli.run_json(['lambda', 'list-functions'])
                lambda_count = len(payload.get('Functions', []))
                lambda_source = 'real-aws-cli'
            except Exception:
                pass

            lambda_rate = rates.get('lambda.invocation', {}).get('price', 0.20)
            lambda_monthly = round(lambda_count * 1 * lambda_rate, 2)
            forecasts.append({
                'service': 'Lambda',
                'resourceType': 'Functions',
                'count': lambda_count,
                'unitPrice': lambda_rate,
                'monthly': lambda_monthly,
                'source': lambda_source,
            })

            # 4. DynamoDB Tables
            ddb_count = 0
            ddb_source = 'fallback-zero'
            try:
                payload = await self.aws_cli.run_json(['dynamodb', 'list-tables'])
                ddb_count = len(payload.get('TableNames', []))
                ddb_source = 'real-aws-cli'
            except Exception:
                if self.compatibility_service:
                    compat = await self.compatibility_service.get_resource('dynamodb', 'tables')
                    ddb_count = compat.get('count', 0) if compat else 0
                    ddb_source = 'sidecar-compat'

            ddb_rate = rates.get('dynamodb.table', {}).get('price', 2.50)
            ddb_monthly = round(ddb_count * ddb_rate, 2)
            forecasts.append({
                'service': 'DynamoDB',
                'resourceType': 'Tables',
                'count': ddb_count,
                'unitPrice': ddb_rate,
                'monthly': ddb_monthly,
                'source': ddb_source,
            })

            # 5. RDS DB Instances
            rds_count = 0
            rds_source = 'fallback-zero'
            try:
                payload = await self.aws_cli.run_json(['rds', 'describe-db-instances'])
                rds_count = len(payload.get('DBInstances', []))
                rds_source = 'real-aws-cli'
            except Exception:
                pass

            rds_rate = rates.get('rds.instance', {}).get('price', 0.017)
            rds_monthly = round(rds_count * 730 * rds_rate, 2)
            forecasts.append({
                'service': 'RDS',
                'resourceType': 'DBInstances',
                'count': rds_count,
                'unitPrice': round(730 * rds_rate, 4),
                'monthly': rds_monthly,
                'source': rds_source,
            })

            total_monthly_forecast = sum(item['monthly'] for item in forecasts)
            total_monthly_forecast = round(total_monthly_forecast, 2)

            return {
                'ok': True,
                'totalMonthlyForecast': total_monthly_forecast,
                'forecasts': forecasts,
            }
        except Exception:
            return {
                'ok': False,
                'totalMonthlyForecast': 0.0,
                'forecasts': [],
            }

    async def run_kms_round_trip(self) -> Dict[str, Any]:
        working_directory = tempfile.mkdtemp(prefix='floci-kms-diag-')
        plaintext_file = os.path.join(working_directory, 'plain.txt')
        ciphertext_file = os.path.join(working_directory, 'cipher.bin')
        plaintext = f"floci-kms-diag-{int(time.time() * 1000)}"
        steps = []

        key_id = None
        decrypted = None
        matches = False

        try:
            with open(plaintext_file, 'w', encoding='utf-8') as f:
                f.write(plaintext)

            # 1. Create a transient key
            async def _create_key():
                response = await self.aws_cli.run_json([
                    'kms', 'create-key',
                    '--description', 'floci-diagnostic round-trip',
                ])
                id_ = response.get('KeyMetadata', {}).get('KeyId')
                if not id_:
                    raise Exception('CreateKey did not return KeyMetadata.KeyId')
                nonlocal key_id
                key_id = id_
                return f"keyId={id_}"

            create_step = await self._timed('create-key', _create_key)
            steps.append(create_step)
            if not create_step['ok'] or not key_id:
                return await self._finish(steps, plaintext, None, False, working_directory, None)

            # 2. Encrypt the canary plaintext
            async def _encrypt():
                abs_plain = os.path.abspath(plaintext_file).replace('\\', '/')
                if not abs_plain.startswith('/'):
                    abs_plain = '/' + abs_plain

                response = await self.aws_cli.run_json([
                    'kms', 'encrypt',
                    '--key-id', key_id,
                    '--plaintext', f"fileb://{abs_plain}",
                ])
                cipher_base64 = response.get('CiphertextBlob')
                if not cipher_base64:
                    raise Exception('Encrypt did not return CiphertextBlob')
                cipher_bytes = base64.b64decode(cipher_base64)
                with open(ciphertext_file, 'wb') as f:
                    f.write(cipher_bytes)
                return f"cipher.bytes={len(cipher_bytes)}"

            encrypt_step = await self._timed('encrypt', _encrypt)
            steps.append(encrypt_step)
            if not encrypt_step['ok']:
                return await self._finish(steps, plaintext, decrypted, matches, working_directory, key_id)

            # 3. Decrypt and verify
            async def _decrypt():
                abs_cipher = os.path.abspath(ciphertext_file).replace('\\', '/')
                if not abs_cipher.startswith('/'):
                    abs_cipher = '/' + abs_cipher

                response = await self.aws_cli.run_json([
                    'kms', 'decrypt',
                    '--ciphertext-blob', f"fileb://{abs_cipher}",
                ])
                decrypted_base64 = response.get('Plaintext')
                if not decrypted_base64:
                    raise Exception('Decrypt did not return Plaintext')
                nonlocal decrypted, matches
                decrypted = base64.b64decode(decrypted_base64).decode('utf-8')
                matches = (decrypted == plaintext)
                return f"matches={matches}"

            decrypt_step = await self._timed('decrypt', _decrypt)
            steps.append(decrypt_step)

            return await self._finish(steps, plaintext, decrypted, matches, working_directory, key_id)
        except Exception as error:
            return await self._finish(steps, plaintext, decrypted, matches, working_directory, key_id, error)

    async def _finish(
        self,
        steps: List[Dict[str, Any]],
        plaintext: str,
        decrypted: Optional[str],
        matches: bool,
        working_directory: str,
        key_id: Optional[str],
        unexpected_error: Optional[Exception] = None
    ) -> Dict[str, Any]:
        cleanup = await self._cleanup(working_directory, key_id)
        if unexpected_error:
            steps.append({
                'name': 'fatal',
                'ok': False,
                'durationMs': 0,
                'error': str(unexpected_error),
            })

        ok = matches and all(step.get('ok') for step in steps)
        return {
            'ok': ok,
            'matches': matches,
            'keyId': key_id,
            'plaintext': plaintext,
            'decrypted': decrypted,
            'steps': steps,
            'cleanup': cleanup,
        }

    async def _cleanup(self, working_directory: str, key_id: Optional[str]) -> Dict[str, Any]:
        cleanup_result = {'ok': True}
        if key_id:
            try:
                await self.aws_cli.run_json([
                    'kms', 'schedule-key-deletion',
                    '--key-id', key_id,
                    '--pending-window-in-days', '7',
                ])
            except Exception as error:
                cleanup_result['ok'] = False
                if isinstance(error, AwsCliError):
                    cleanup_result['error'] = error.stderr.strip() or str(error)
                else:
                    cleanup_result['error'] = str(error)

        try:
            shutil.rmtree(working_directory, ignore_errors=True)
        except Exception:
            cleanup_result['ok'] = False
            prev_err = cleanup_result.get('error')
            cleanup_result['error'] = (f"{prev_err}; " if prev_err else "") + 'failed to remove temp directory'

        return cleanup_result

    async def get_performance_stats(self) -> Dict[str, Any]:
        import asyncio
        import docker

        def _fetch_stats():
            client = docker.from_env()
            containers = client.containers.list()
            stats_list = []
            for c in containers:
                try:
                    stats = c.stats(stream=False)

                    # Calculate CPU %
                    cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
                    system_cpu_delta = stats['cpu_stats']['system_cpu_usage'] - stats.get('precpu_stats', {}).get('system_cpu_usage', 0)
                    number_cpus = stats['cpu_stats'].get('online_cpus', len(stats['cpu_stats']['cpu_usage'].get('percpu_usage', [1])))
                    cpu_percent = 0.0
                    if system_cpu_delta > 0.0 and cpu_delta > 0.0:
                        cpu_percent = (cpu_delta / system_cpu_delta) * number_cpus * 100.0

                    # Calculate Memory %
                    mem_usage = stats['memory_stats'].get('usage', 0)
                    # Exclude cache if possible
                    if 'stats' in stats['memory_stats'] and 'cache' in stats['memory_stats']['stats']:
                        mem_usage -= stats['memory_stats']['stats']['cache']
                    mem_limit = stats['memory_stats'].get('limit', 0)

                    stats_list.append({
                        'id': c.short_id,
                        'name': c.name,
                        'status': c.status,
                        'cpu_percent': round(cpu_percent, 2),
                        'memory_usage_bytes': mem_usage,
                        'memory_limit_bytes': mem_limit
                    })
                except Exception:
                    pass
            return stats_list

        try:
            stats_list = await asyncio.to_thread(_fetch_stats)
            return {
                'ok': True,
                'containers': stats_list
            }
        except Exception as e:
            return {
                'ok': False,
                'error': str(e),
                'containers': []
            }

    async def _timed(self, name: str, fn) -> Dict[str, Any]:
        started_at = int(time.time() * 1000)
        try:
            detail = await fn()
            result = {
                'name': name,
                'ok': True,
                'durationMs': int(time.time() * 1000) - started_at,
            }
            if isinstance(detail, str):
                result['detail'] = detail
            return result
        except Exception as error:
            message = str(error)
            if isinstance(error, AwsCliError):
                message = error.stderr.strip() or str(error)
            return {
                'name': name,
                'ok': False,
                'durationMs': int(time.time() * 1000) - started_at,
                'error': message,
            }
