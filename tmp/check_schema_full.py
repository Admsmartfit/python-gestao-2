import os
from sqlalchemy import create_engine, inspect

db_path = r'c:\Users\ralan\python gestao 2\gmm\instance\gmm.db'
engine = create_engine(f"sqlite:///{db_path}")
inspector = inspect(engine)
columns = inspector.get_columns('pedidos_compra')

print("--- Column List ---")
for col in columns:
    print(f"Name: {col['name']}, Nullable: {col['nullable']}")
print("--- End ---")
