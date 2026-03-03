import os
from sqlalchemy import create_engine, inspect

db_path = r'c:\Users\ralan\python gestao 2\gmm\instance\gmm.db'
engine = create_engine(f"sqlite:///{db_path}")
inspector = inspect(engine)
columns = inspector.get_columns('pedidos_compra')

with open(r'c:\Users\ralan\python gestao 2\tmp\schema_results.txt', 'w') as f:
    f.write("--- Column List ---\n")
    for col in columns:
        f.write(f"Name: {col['name']}, Nullable: {col['nullable']}\n")
    f.write("--- End ---\n")
