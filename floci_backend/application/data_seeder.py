import asyncio
import json
import logging
from typing import Optional, Dict, Any, List
from floci_backend.config import config
import boto3
import asyncpg
import urllib.parse
from faker import Faker

fake = Faker()

class DataSeeder:
    def __init__(self):
        self.endpoint_url = config.aws_endpoint_url
        self.region = config.aws_region
        self.access_key = config.aws_access_key_id
        self.secret_key = config.aws_secret_access_key

    def _get_client(self, service_name: str):
        return boto3.client(
            service_name,
            endpoint_url=self.endpoint_url,
            region_name=self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key
        )

    def _quote_ident(self, ident: str) -> str:
        return f'"{ident}"'

    async def seed_postgres(self, db_url: str, table_name: str, records: list[Dict[str, Any]]):
        async_url = db_url.replace("postgresql://", "postgresql+asyncpg://") if "postgresql://" in db_url else db_url

        parsed = urllib.parse.urlparse(db_url)
        user = parsed.username
        password = parsed.password
        host = parsed.hostname
        port = parsed.port or 5432
        database = parsed.path.lstrip('/')

        conn = await asyncpg.connect(user=user, password=password, database=database, host=host, port=port)
        try:
            for record in records:
                columns = ', '.join([self._quote_ident(k) for k in record.keys()])
                placeholders = ', '.join([f'${i+1}' for i in range(len(record))])
                values = list(record.values())

                # Quote table name as well
                q_table = self._quote_ident(table_name)
                query = f"INSERT INTO {q_table} ({columns}) VALUES ({placeholders})"
                await conn.execute(query, *values)
        finally:
            await conn.close()

    async def _deduce_postgres_schema(self, conn, table_name: str) -> List[Dict[str, Any]]:
        query = "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = $1;"
        columns = await conn.fetch(query, table_name)
        if not columns:
            return []

        records = []
        for _ in range(10): # Generate 10 records
            mock_record = {}
            for col in columns:
                col_name = col['column_name']
                data_type = col['data_type']

                if 'int' in data_type:
                    mock_record[col_name] = fake.random_int(min=1, max=1000)
                elif 'bool' in data_type:
                    mock_record[col_name] = fake.boolean()
                elif 'date' in data_type or 'timestamp' in data_type:
                    mock_record[col_name] = fake.date_time().isoformat()
                elif 'uuid' in data_type:
                    mock_record[col_name] = fake.uuid4()
                else:
                    if 'name' in col_name.lower():
                        mock_record[col_name] = fake.name()
                    elif 'email' in col_name.lower():
                        mock_record[col_name] = fake.email()
                    elif 'phone' in col_name.lower():
                        mock_record[col_name] = fake.phone_number()
                    elif 'address' in col_name.lower() or 'city' in col_name.lower() or 'street' in col_name.lower():
                        mock_record[col_name] = fake.address()
                    else:
                        mock_record[col_name] = fake.word()
            records.append(mock_record)

        return records

    async def seed_dynamodb(self, table_name: str, records: list[Dict[str, Any]]):
        client = self._get_client('dynamodb')
        for record in records:
            item = {}
            for k, v in record.items():
                if isinstance(v, str):
                    item[k] = {'S': v}
                elif isinstance(v, (int, float)):
                    item[k] = {'N': str(v)}
                elif isinstance(v, bool):
                    item[k] = {'BOOL': v}
            client.put_item(TableName=table_name, Item=item)

    async def seed_s3(self, bucket_name: str, prefix: str, records: list[Dict[str, Any]]):
        client = self._get_client('s3')
        for i, record in enumerate(records):
            client.put_object(
                Bucket=bucket_name,
                Key=f"{prefix}/record_{i}.json",
                Body=json.dumps(record)
            )

    async def auto_seed(self, target: str, target_name: str, connection_string: Optional[str] = None, custom_schema: Optional[Dict] = None):
        records = []
        if custom_schema:
            # Generate 10 records matching the shape of custom_schema using faker
            for _ in range(10):
                rec = {}
                for k, v in custom_schema.items():
                    if isinstance(v, str) and v.startswith('faker.'):
                        method = v.split('.')[1]
                        try:
                            rec[k] = getattr(fake, method)()
                        except AttributeError:
                            rec[k] = fake.word()
                    else:
                        rec[k] = v
                records.append(rec)

        if target.lower() == 'postgres':
            if not connection_string:
                raise ValueError("connection_string is required for postgres")

            if not records:
                parsed = urllib.parse.urlparse(connection_string)
                conn = await asyncpg.connect(
                    user=parsed.username, password=parsed.password,
                    database=parsed.path.lstrip('/'), host=parsed.hostname, port=parsed.port or 5432
                )
                try:
                    records = await self._deduce_postgres_schema(conn, target_name)
                    if not records:
                        return {"status": "error", "message": f"Could not deduce schema for table {target_name}"}
                finally:
                    await conn.close()

            await self.seed_postgres(connection_string, target_name, records)
            return {"status": "success", "message": f"Seeded {len(records)} records into postgres table {target_name}"}

        elif target.lower() == 'dynamodb':
            if not records:
                records = [{"id": fake.uuid4(), "name": fake.name()} for _ in range(10)]
            await self.seed_dynamodb(target_name, records)
            return {"status": "success", "message": f"Seeded {len(records)} records into dynamodb table {target_name}"}

        elif target.lower() == 's3':
            if not records:
                records = [{"id": fake.uuid4(), "data": fake.text()} for _ in range(10)]
            await self.seed_s3(target_name, "mock_data", records)
            return {"status": "success", "message": f"Seeded {len(records)} objects into s3 bucket {target_name}"}
        else:
            raise ValueError(f"Unsupported target: {target}")
