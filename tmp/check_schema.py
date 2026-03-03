import os
from sqlalchemy import create_engine, inspect

db_path = r'c:\Users\ralan\python gestao 2\gmm\instance\gmm.db'
engine = create_engine(f"sqlite:///{db_path}")
inspector = inspect(engine)
columns = inspector.get_columns('pedidos_compra')

for col in columns:
    if col['name'] == 'estoque_id':
        print(f"ESTOQUE_ID_NULLABLE: {col['nullable']}")
    if not col['nullable']:
        print(f"NOT_NULL_COLUMN: {col['name']}")
