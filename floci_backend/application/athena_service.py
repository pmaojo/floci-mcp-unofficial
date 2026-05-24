import asyncio
import json
import random
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from floci_backend.infrastructure.aws_cli import AwsCli, AwsCliError
from floci_backend.infrastructure.json_state_store import JsonStateStore

class AthenaService:
    def __init__(self, aws_cli: AwsCli):
        self.aws_cli = aws_cli
        self.history_store = JsonStateStore[Dict[str, Any]](
            'athena-history.json',
            dict,
            {'history': []}
        )

    async def get_catalog(self) -> Dict[str, Any]:
        try:
            return await self._list_catalogs()
        except Exception:
            return {'databases': []}

    async def _list_catalogs(self) -> Dict[str, Any]:
        try:
            response = await self.aws_cli.run_json(['glue', 'get-databases'])
            db_list = response.get('DatabaseList', [])
        except Exception:
            db_list = []

        databases = []
        for db in db_list:
            db_name = db.get('Name')
            if not db_name:
                continue

            try:
                tables_response = await self.aws_cli.run_json(['glue', 'get-tables', '--database-name', db_name])
                tables_data = tables_response.get('TableList', [])
            except Exception:
                tables_data = []

            tables = []
            for t in tables_data:
                t_name = t.get('Name')
                if not t_name:
                    continue

                columns = []
                for col in t.get('StorageDescriptor', {}).get('Columns', []):
                    if col.get('Name') and col.get('Type'):
                        columns.append({
                            'name': col['Name'],
                            'type': col['Type']
                        })
                tables.append({
                    'name': t_name,
                    'columns': columns
                })

            databases.append({
                'name': db_name,
                'tables': tables
            })

        return {'databases': databases}

    async def start_query(self, query: str, database: str, work_group: str = 'primary') -> Dict[str, Any]:
        if not query or not query.strip():
            raise ValueError('Query string is required')

        execution_id = f"q-{random.randint(1000, 9999)}-{int(datetime.utcnow().timestamp())}"

        record = {
            'id': execution_id,
            'query': query,
            'database': database,
            'status': 'QUEUED',
            'submittedAt': datetime.utcnow().isoformat() + "Z"
        }

        def mutator(state):
            history = state.get('history', [])
            history.insert(0, record)
            if len(history) > 100:
                history = history[:100]
            state['history'] = history
            return state

        await self.history_store.update(mutator)

        asyncio.create_task(self._process_query(execution_id))

        return {'queryExecutionId': execution_id}

    async def get_query_status(self, execution_id: str) -> Dict[str, Any]:
        state = await self.history_store.read()
        history = state.get('history', [])
        exec_record = next((h for h in history if h['id'] == execution_id), None)
        if not exec_record:
            raise ValueError('Query execution not found')
        return exec_record

    async def get_query_results(self, execution_id: str) -> Dict[str, Any]:
        exec_record = await self.get_query_status(execution_id)
        if exec_record.get('status') != 'SUCCEEDED':
            raise ValueError('Query has not succeeded yet')
        return exec_record.get('results', {'columns': [], 'rows': []})

    async def get_history(self) -> List[Dict[str, Any]]:
        state = await self.history_store.read()
        return state.get('history', [])

    async def clear_history(self) -> None:
        def mutator(state):
            state['history'] = []
            return state
        await self.history_store.update(mutator)

    async def _process_query(self, execution_id: str):
        await asyncio.sleep(0.5)

        async def update_state(updates):
            def mutator(state):
                history = state.get('history', [])
                for idx, h in enumerate(history):
                    if h['id'] == execution_id:
                        history[idx] = {**h, **updates}
                        break
                state['history'] = history
                return state
            await self.history_store.update(mutator)

        await update_state({'status': 'RUNNING'})

        state = await self.history_store.read()
        exec_record = next((h for h in state.get('history', []) if h['id'] == execution_id), None)
        if not exec_record:
            return

        start_time = datetime.utcnow()
        try:
            query = exec_record['query']
            db = exec_record['database']
            results = await self._emulate_query(query, db)

            await update_state({
                'status': 'SUCCEEDED',
                'completedAt': datetime.utcnow().isoformat() + "Z",
                'durationMs': int((datetime.utcnow() - start_time).total_seconds() * 1000) + 250,
                'results': results
            })
        except Exception as e:
            await update_state({
                'status': 'FAILED',
                'errorMessage': str(e),
                'completedAt': datetime.utcnow().isoformat() + "Z",
                'durationMs': int((datetime.utcnow() - start_time).total_seconds() * 1000)
            })

    async def _emulate_query(self, sql: str, database: str) -> Dict[str, Any]:
        cleaned = re.sub(r'\s+', ' ', sql).strip()
        clean_lower = cleaned.lower()

        # 1. SHOW DATABASES
        if clean_lower.startswith('show databases'):
            catalog = await self._list_catalogs()
            return {
                'columns': [{'name': 'database_name', 'type': 'string'}],
                'rows': [[d['name']] for d in catalog.get('databases', [])]
            }

        # 2. SHOW TABLES
        if clean_lower.startswith('show tables'):
            catalog = await self._list_catalogs()
            target_db = next((d for d in catalog.get('databases', []) if d['name'] == database), None)
            if not target_db and catalog.get('databases'):
                target_db = catalog['databases'][0]
            if not target_db:
                return {'columns': [{'name': 'tab_name', 'type': 'string'}], 'rows': []}
            return {
                'columns': [{'name': 'tab_name', 'type': 'string'}],
                'rows': [[t['name']] for t in target_db.get('tables', [])]
            }

        # 3. DESCRIBE
        if clean_lower.startswith('describe ') or clean_lower.startswith('describe table '):
            parts = cleaned.split(' ')
            table_name = parts[-1].replace(';', '').strip()

            catalog = await self._list_catalogs()
            target_db = next((d for d in catalog.get('databases', []) if d['name'] == database), None)
            if not target_db and catalog.get('databases'):
                target_db = catalog['databases'][0]

            if not target_db:
                raise ValueError(f"Database {database} not found")

            table = next((t for t in target_db.get('tables', []) if t['name'].lower() == table_name.lower()), None)
            if not table:
                raise ValueError(f"Table not found in database {target_db['name']}: {table_name}")

            return {
                'columns': [
                    {'name': 'col_name', 'type': 'string'},
                    {'name': 'data_type', 'type': 'string'},
                    {'name': 'comment', 'type': 'string'}
                ],
                'rows': [[col['name'], col['type'], 'Emulated column description'] for col in table.get('columns', [])]
            }

        # 4. SELECT
        if clean_lower.startswith('select'):
            limit = 50
            limit_match = re.search(r'limit\s+(\d+)', clean_lower)
            if limit_match:
                limit = int(limit_match.group(1))
            if limit > 1000:
                limit = 1000

            from_index = clean_lower.find(' from ')
            if from_index == -1:
                return {
                    'columns': [{'name': '_col0', 'type': 'int'}],
                    'rows': [['1']]
                }

            after_from = cleaned[from_index + 6:].strip()
            stop_words = ['where', 'group', 'order', 'limit', 'join', 'left', 'right', 'inner', ';']
            table_part = after_from
            for word in stop_words:
                idx = table_part.lower().find(' ' + word)
                if idx != -1:
                    table_part = table_part[:idx]
            table_part = table_part.replace(';', '').strip()

            target_db_name = database
            table_name = table_part
            if '.' in table_part:
                dots = table_part.split('.')
                target_db_name = dots[0]
                table_name = dots[1]

            catalog = await self._list_catalogs()
            target_db = next((d for d in catalog.get('databases', []) if d['name'].lower() == target_db_name.lower()), None)
            if not target_db and catalog.get('databases'):
                target_db = catalog['databases'][0]

            if not target_db:
                raise ValueError(f"Database {target_db_name} not found")

            table = next((t for t in target_db.get('tables', []) if t['name'].lower() == table_name.lower()), None)
            if not table:
                raise ValueError(f"Table not found: {target_db_name}.{table_name}. Check spelling or Glue catalogs.")

            rows = self._generate_mock_rows(table['name'], table.get('columns', []), limit, clean_lower)
            return {
                'columns': table.get('columns', []),
                'rows': rows
            }

        raise ValueError('Unsupported emulator SQL query syntax. Use SELECT, SHOW TABLES, SHOW DATABASES, or DESCRIBE.')

    def _generate_mock_rows(self, table_name: str, columns: List[Dict[str, str]], limit: int, clean_sql: str) -> List[List[str]]:
        rows = []

        filter_status = 200 if 'status = 200' in clean_sql else (404 if 'status = 404' in clean_sql else None)
        filter_method = 'GET' if "method = 'get'" in clean_sql else ('POST' if "method = 'post'" in clean_sql else None)

        ips = ['192.168.1.45', '10.0.0.12', '172.16.89.2', '8.8.8.8', '192.168.0.101', '127.0.0.1']
        uris = ['/index.html', '/api/v1/users', '/login', '/dashboard', '/static/logo.png', '/api/v1/health', '/products/item-39']
        methods = ['GET', 'POST', 'PUT', 'DELETE']
        statuses = [200, 200, 200, 200, 200, 302, 404, 500]

        event_types = ['page_view', 'page_view', 'click', 'add_to_cart', 'remove_from_cart', 'checkout', 'purchase_complete']
        referrers = ['https://google.com', 'https://github.com', 'https://twitter.com', 'direct', 'https://news.ycombinator.com']
        devices = ['mobile', 'mobile', 'desktop', 'desktop', 'tablet']

        services = ['AmazonEC2', 'AmazonS3', 'AWSLambda', 'AmazonRDS', 'AmazonDynamoDB', 'AmazonRoute53']
        usage_types = ['BoxUsage:t3.micro', 'TimedStorage-ByteHrs', 'Lambda-GB-Second', 'InstanceUsage:db.t3.micro', 'TableProvisionedCapacity', 'HostedZone-Month']
        base_costs = [0.0104, 0.023, 0.000016, 0.017, 2.50, 0.50]

        for i in range(limit):
            record = []
            for col in columns:
                col_lower = col['name'].lower()
                col_type = col['type'].lower()

                if table_name.lower() == 'web_logs':
                    if col_lower == 'timestamp':
                        record.append((datetime.utcnow() - timedelta(minutes=i)).isoformat() + "Z")
                    elif col_lower == 'ip':
                        record.append(ips[i % len(ips)])
                    elif col_lower == 'method':
                        record.append(filter_method or methods[i % len(methods)])
                    elif col_lower == 'uri':
                        record.append(uris[i % len(uris)])
                    elif col_lower == 'status':
                        record.append(str(filter_status or statuses[i % len(statuses)]))
                    elif col_lower == 'bytes':
                        record.append(str(random.randint(120, 8620)))
                    else:
                        record.append(f"val-{i}")
                elif table_name.lower() == 'clickstream_data':
                    if col_lower == 'session_id':
                        record.append(f"sess-{random.randint(100000, 999999)}")
                    elif col_lower == 'user_id':
                        record.append(f"usr-{2000 + (i % 25)}")
                    elif col_lower == 'event_type':
                        record.append(event_types[i % len(event_types)])
                    elif col_lower == 'referrer':
                        record.append(referrers[i % len(referrers)])
                    elif col_lower == 'device':
                        record.append(devices[i % len(devices)])
                    else:
                        record.append(f"val-{i}")
                elif table_name.lower() == 'billing_reports':
                    if col_lower == 'billing_period':
                        record.append('2026-05')
                    elif col_lower == 'service':
                        record.append(services[i % len(services)])
                    elif col_lower == 'usage_type':
                        record.append(usage_types[i % len(usage_types)])
                    elif col_lower == 'cost':
                        base = base_costs[i % len(base_costs)]
                        multiplier = random.randint(1, 150)
                        record.append(f"{base * multiplier:.4f}")
                    elif col_lower == 'currency':
                        record.append('USD')
                    else:
                        record.append(f"val-{i}")
                else:
                    if 'int' in col_type or 'long' in col_type:
                        record.append(str(random.randint(1, 1000)))
                    elif 'double' in col_type or 'float' in col_type or 'decimal' in col_type:
                        record.append(f"{random.random() * 100:.2f}")
                    elif 'bool' in col_type:
                        record.append('true' if random.random() > 0.5 else 'false')
                    elif 'date' in col_type or 'time' in col_type:
                        record.append((datetime.utcnow() - timedelta(hours=i)).isoformat() + "Z")
                    else:
                        record.append(f"{col['name']}-val-{i}")
            rows.append(record)

        return rows
